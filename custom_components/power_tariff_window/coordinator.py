"""Coordinator for HA Dynamic Energy."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALIGN_TO_HOUR,
    CONF_HOURS,
    CONF_MODE,
    CONF_PRICE_SENSOR,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_ALIGN_TO_HOUR,
    DEFAULT_HOURS,
    DEFAULT_MODE,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    MODE_CHEAPEST,
)
from .models import PriceSlot, TariffPlan

_LOGGER = logging.getLogger(__name__)


class TariffWindowCoordinator(DataUpdateCoordinator[TariffPlan]):
    """Compute cheapest/most expensive slots in a time window."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"HA Dynamic Energy ({config_entry.entry_id})",
            update_interval=timedelta(minutes=5),
        )
        self.config_entry = config_entry

    async def _async_update_data(self) -> TariffPlan:
        """Fetch sensor data and compute plan."""
        price_entity = self._get_value(CONF_PRICE_SENSOR)
        mode = self._get_value(CONF_MODE, DEFAULT_MODE)
        hours = int(self._get_value(CONF_HOURS, DEFAULT_HOURS))
        window_start = _parse_time(self._get_value(CONF_WINDOW_START, DEFAULT_WINDOW_START))
        window_end = _parse_time(self._get_value(CONF_WINDOW_END, DEFAULT_WINDOW_END))
        align_to_hour = bool(self._get_value(CONF_ALIGN_TO_HOUR, DEFAULT_ALIGN_TO_HOUR))

        state = self.hass.states.get(price_entity)
        if state is None:
            _LOGGER.warning("Price sensor '%s' not found", price_entity)
            return _empty_plan()

        tz = dt_util.get_time_zone(self.hass.config.time_zone) or dt_util.UTC
        slots = _extract_slots(state.attributes, tz)
        if not slots:
            _LOGGER.warning(
                "No usable price slots found in '%s' attributes (expected raw_today/raw_tomorrow or today/tomorrow)",
                price_entity,
            )
            return _empty_plan()

        now = dt_util.now().astimezone(tz)
        selected = _select_slots(
            slots=slots,
            now=now,
            mode=mode,
            hours=hours,
            window_start=window_start,
            window_end=window_end,
            align_to_hour=align_to_hour,
        )

        active_ranges = _merge_selected_slots(selected)
        active = _is_active(now, selected)
        next_switch = _next_switch_moment(now, selected)
        next_active_start = _next_active_start(now, active_ranges)
        active_until = _active_until(now, active_ranges)
        selected_window_start = selected[0].start if selected else None
        selected_window_end = selected[-1].end if selected else None
        selected_window_total_price = _window_total_price(selected) if selected else None
        return TariffPlan(
            active=active,
            next_switch=next_switch,
            selected_window_start=selected_window_start,
            selected_window_end=selected_window_end,
            selected_window_total_price=selected_window_total_price,
            next_active_start=next_active_start,
            active_until=active_until,
            minutes_until_active=_minutes_until(now, next_active_start),
            minutes_remaining_active=_minutes_until(now, active_until),
            selected_slots=selected,
        )

    def _get_value(self, key: str, default: str | int | None = None) -> str | int | None:
        """Return option value with data fallback."""
        if key in self.config_entry.options:
            return self.config_entry.options[key]
        return self.config_entry.data.get(key, default)


def _parse_time(value: str | time) -> time:
    """Parse time from config flow string."""
    if isinstance(value, time):
        return value
    return time.fromisoformat(value)


def _empty_plan() -> TariffPlan:
    """Return an empty plan when no data is available."""
    return TariffPlan(
        active=False,
        next_switch=None,
        selected_window_start=None,
        selected_window_end=None,
        selected_window_total_price=None,
        next_active_start=None,
        active_until=None,
        minutes_until_active=0,
        minutes_remaining_active=0,
        selected_slots=[],
    )


def _extract_slots(attributes: dict, tz) -> list[PriceSlot]:
    """Extract hourly slots from Nord Pool style attributes."""
    raw_slots: list[PriceSlot] = []

    for key in ("raw_today", "raw_tomorrow"):
        raw = attributes.get(key)
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                start = _parse_dt(item.get("start"), tz)
                end = _parse_dt(item.get("end"), tz)
                value = item.get("value", item.get("price"))
                if start is None or end is None or value is None:
                    continue
                try:
                    raw_slots.append(PriceSlot(start=start, end=end, price=float(value)))
                except (TypeError, ValueError):
                    continue

    if raw_slots:
        return _normalize_to_hourly_slots(sorted(raw_slots, key=lambda item: item.start))

    # Fallback: some sensors expose "today"/"tomorrow" as 24-value lists.
    today_values = attributes.get("today")
    tomorrow_values = attributes.get("tomorrow")
    now_local = dt_util.now().astimezone(tz)
    midnight_today = datetime.combine(now_local.date(), time(0, 0, 0), tzinfo=tz)
    slots: list[PriceSlot] = []

    def add_simple_day(values: list, day_offset: int) -> None:
        if not isinstance(values, list):
            return
        day_start = midnight_today + timedelta(days=day_offset)
        slot_duration = _infer_slot_duration(len(values))
        for idx, value in enumerate(values):
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            start = day_start + (slot_duration * idx)
            end = start + slot_duration
            slots.append(PriceSlot(start=start, end=end, price=price))

    add_simple_day(today_values, 0)
    add_simple_day(tomorrow_values, 1)
    return _normalize_to_hourly_slots(sorted(slots, key=lambda item: item.start))


def _parse_dt(raw_value, tz) -> datetime | None:
    """Parse datetime value from attribute content."""
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        dt_value = raw_value
    elif isinstance(raw_value, str):
        try:
            dt_value = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=tz)
    return dt_value.astimezone(tz)


def _infer_slot_duration(value_count: int) -> timedelta:
    """Infer price slot duration from the number of values in one day."""
    if value_count <= 0:
        return timedelta(hours=1)
    return timedelta(days=1) / value_count


def _normalize_to_hourly_slots(slots: list[PriceSlot]) -> list[PriceSlot]:
    """Aggregate quarter-hour or half-hour prices into hourly slots."""
    if not slots:
        return []

    first_duration = slots[0].end - slots[0].start
    if first_duration == timedelta(hours=1):
        return slots

    hourly_slots: list[PriceSlot] = []
    slot_map = {slot.start: slot for slot in slots}
    current = slots[0].start.replace(minute=0, second=0, microsecond=0)
    final_end = max(slot.end for slot in slots)

    while current < final_end:
        hour_end = current + timedelta(hours=1)
        cursor = current
        weighted_total = 0.0
        covered = timedelta(0)

        while cursor < hour_end:
            slot = slot_map.get(cursor)
            if slot is None:
                break
            duration = slot.end - slot.start
            weighted_total += slot.price * duration.total_seconds()
            covered += duration
            cursor = slot.end

        if covered == timedelta(hours=1):
            hourly_slots.append(
                PriceSlot(
                    start=current,
                    end=hour_end,
                    price=weighted_total / covered.total_seconds(),
                )
            )

        current = hour_end

    return hourly_slots


def _select_slots(
    slots: list[PriceSlot],
    now: datetime,
    mode: str,
    hours: int,
    window_start: time,
    window_end: time,
    align_to_hour: bool,
) -> list[PriceSlot]:
    """Select the best contiguous block for today and tomorrow windows."""
    selected: list[PriceSlot] = []

    for day in (now.date(), now.date() + timedelta(days=1)):
        selected.extend(
            _best_contiguous_block_for_window(
                slots=slots,
                day=day,
                window_start=window_start,
                window_end=window_end,
                hours=hours,
                mode=mode,
                align_to_hour=align_to_hour,
            )
        )

    selected.sort(key=lambda item: item.start)
    return selected


def _best_contiguous_block_for_window(
    slots: list[PriceSlot],
    day: date,
    window_start: time,
    window_end: time,
    hours: int,
    mode: str,
    align_to_hour: bool,
) -> list[PriceSlot]:
    """Return the best contiguous block inside one configured window."""
    if not slots:
        return []

    first_slot = slots[0]
    start_dt = datetime.combine(day, window_start, tzinfo=first_slot.start.tzinfo)
    if window_end <= window_start:
        end_dt = datetime.combine(day + timedelta(days=1), window_end, tzinfo=start_dt.tzinfo)
    else:
        end_dt = datetime.combine(day, window_end, tzinfo=start_dt.tzinfo)

    slot_map = {slot.start: slot for slot in slots}
    required_duration = timedelta(hours=hours)
    latest_start = end_dt - required_duration

    if hours <= 0 or latest_start < start_dt:
        return []

    best_block: list[PriceSlot] = []
    best_score: float | None = None
    prefer_lower = mode == MODE_CHEAPEST

    for slot in slots:
        if slot.start < start_dt or slot.start > latest_start:
            continue
        if align_to_hour and slot.start.minute != 0:
            continue

        block, weighted_cost = _collect_block(slot_map, slot.start, required_duration)
        if not block:
            continue

        if best_score is None:
            best_block = block
            best_score = weighted_cost
            continue

        if prefer_lower and weighted_cost < best_score:
            best_block = block
            best_score = weighted_cost
            continue

        if not prefer_lower and weighted_cost > best_score:
            best_block = block
            best_score = weighted_cost

    return best_block


def _collect_block(
    slot_map: dict[datetime, PriceSlot],
    start: datetime,
    required_duration: timedelta,
) -> tuple[list[PriceSlot], float]:
    """Collect a contiguous block starting at one specific time."""
    block: list[PriceSlot] = []
    weighted_cost = 0.0
    covered = timedelta(0)
    cursor = start

    while covered < required_duration:
        slot = slot_map.get(cursor)
        if slot is None:
            return [], 0.0
        duration = slot.end - slot.start
        block.append(slot)
        covered += duration
        weighted_cost += slot.price * duration.total_seconds()
        cursor = slot.end

    if covered != required_duration:
        return [], 0.0

    return block, weighted_cost


def _window_total_price(slots: list[PriceSlot]) -> float:
    """Return total price over the selected window for a constant 1 kW load."""
    return sum(
        slot.price * ((slot.end - slot.start).total_seconds() / 3600)
        for slot in slots
    )


def _is_active(now: datetime, slots: list[PriceSlot]) -> bool:
    """Return true if now is inside one of the selected slots."""
    return any(slot.start <= now < slot.end for slot in slots)


def _next_switch_moment(now: datetime, slots: list[PriceSlot]) -> datetime | None:
    """Find next moment where active state changes."""
    if not slots:
        return None

    boundaries = sorted({point for slot in slots for point in (slot.start, slot.end) if point > now})
    if not boundaries:
        return None

    for boundary in boundaries:
        before = _is_active(boundary - timedelta(seconds=1), slots)
        after = _is_active(boundary + timedelta(seconds=1), slots)
        if before != after:
            return boundary
    return None


def _merge_selected_slots(slots: list[PriceSlot]) -> list[tuple[datetime, datetime]]:
    """Merge adjacent selected hourly slots into active ranges."""
    if not slots:
        return []

    ranges: list[tuple[datetime, datetime]] = []
    current_start = slots[0].start
    current_end = slots[0].end

    for slot in slots[1:]:
        if slot.start == current_end:
            current_end = slot.end
            continue
        ranges.append((current_start, current_end))
        current_start = slot.start
        current_end = slot.end

    ranges.append((current_start, current_end))
    return ranges


def _next_active_start(now: datetime, active_ranges: list[tuple[datetime, datetime]]) -> datetime | None:
    """Return the next future active range start."""
    for start, end in active_ranges:
        if start <= now < end:
            return start
        if start > now:
            return start
    return None


def _active_until(now: datetime, active_ranges: list[tuple[datetime, datetime]]) -> datetime | None:
    """Return the end of the currently active range."""
    for start, end in active_ranges:
        if start <= now < end:
            return end
    return None


def _minutes_until(now: datetime, moment: datetime | None) -> int:
    """Return whole minutes until a moment, clamped at zero."""
    if moment is None or moment <= now:
        return 0
    return int((moment - now).total_seconds() // 60)
