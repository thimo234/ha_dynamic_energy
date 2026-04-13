"""Coordinator for HA Dynamic Energy."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HOURS,
    CONF_MODE,
    CONF_PRICE_SENSOR,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
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
        )

        active_ranges = _merge_selected_slots(selected)
        active = _is_active(now, selected)
        next_switch = _next_switch_moment(now, selected)
        next_active_start = _next_active_start(now, active_ranges)
        active_until = _active_until(now, active_ranges)
        return TariffPlan(
            active=active,
            next_switch=next_switch,
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
        next_active_start=None,
        active_until=None,
        minutes_until_active=0,
        minutes_remaining_active=0,
        selected_slots=[],
    )


def _extract_slots(attributes: dict, tz) -> list[PriceSlot]:
    """Extract hourly slots from Nord Pool style attributes."""
    slots: list[PriceSlot] = []

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
                    slots.append(PriceSlot(start=start, end=end, price=float(value)))
                except (TypeError, ValueError):
                    continue

    if slots:
        return sorted(slots, key=lambda item: item.start)

    # Fallback: some sensors expose "today"/"tomorrow" as 24-value lists.
    today_values = attributes.get("today")
    tomorrow_values = attributes.get("tomorrow")
    now_local = dt_util.now().astimezone(tz)
    midnight_today = datetime.combine(now_local.date(), time(0, 0, 0), tzinfo=tz)

    def add_simple_day(values: list, day_offset: int) -> None:
        if not isinstance(values, list):
            return
        day_start = midnight_today + timedelta(days=day_offset)
        for idx, value in enumerate(values):
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            start = day_start + timedelta(hours=idx)
            end = start + timedelta(hours=1)
            slots.append(PriceSlot(start=start, end=end, price=price))

    add_simple_day(today_values, 0)
    add_simple_day(tomorrow_values, 1)
    return sorted(slots, key=lambda item: item.start)


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


def _select_slots(
    slots: list[PriceSlot],
    now: datetime,
    mode: str,
    hours: int,
    window_start: time,
    window_end: time,
) -> list[PriceSlot]:
    """Select the best contiguous block for today and tomorrow windows."""
    by_start = {slot.start: slot for slot in slots}
    selected: list[PriceSlot] = []

    for day in (now.date(), now.date() + timedelta(days=1)):
        in_window = _slots_in_window(by_start, day, window_start, window_end)
        if not in_window:
            continue

        selected.extend(_best_contiguous_block(in_window, hours, mode))

    selected.sort(key=lambda item: item.start)
    return selected


def _slots_in_window(
    by_start: dict[datetime, PriceSlot],
    day: date,
    window_start: time,
    window_end: time,
) -> list[PriceSlot]:
    """Get all full-hour slots whose start is in the configured window."""
    first_slot = next(iter(by_start.values()))
    start_dt = datetime.combine(day, window_start, tzinfo=first_slot.start.tzinfo)
    if window_end <= window_start:
        end_dt = datetime.combine(day + timedelta(days=1), window_end, tzinfo=start_dt.tzinfo)
    else:
        end_dt = datetime.combine(day, window_end, tzinfo=start_dt.tzinfo)

    items: list[PriceSlot] = []
    cursor = start_dt
    while cursor < end_dt:
        slot = by_start.get(cursor)
        if slot is not None:
            items.append(slot)
        cursor += timedelta(hours=1)
    return items


def _best_contiguous_block(
    slots: list[PriceSlot],
    hours: int,
    mode: str,
) -> list[PriceSlot]:
    """Return the best contiguous block of the requested length."""
    if hours <= 0 or len(slots) < hours:
        return []

    best_block: list[PriceSlot] = []
    best_score: float | None = None
    prefer_lower = mode == MODE_CHEAPEST

    for start_index in range(len(slots) - hours + 1):
        block = slots[start_index : start_index + hours]
        if not _is_contiguous_block(block):
            continue

        score = sum(slot.price for slot in block)
        if best_score is None:
            best_block = block
            best_score = score
            continue

        if prefer_lower and score < best_score:
            best_block = block
            best_score = score
            continue

        if not prefer_lower and score > best_score:
            best_block = block
            best_score = score

    return best_block


def _is_contiguous_block(slots: list[PriceSlot]) -> bool:
    """Check whether all slots in a block are adjacent."""
    return all(
        current.end == nxt.start
        for current, nxt in zip(slots, slots[1:], strict=False)
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
