"""Sensor platform for HA Dynamic Energy."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TariffWindowCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from config entry."""
    coordinator: TariffWindowCoordinator = entry.runtime_data
    async_add_entities(
        [
            TariffWindowSelectedWindowSensor(entry, coordinator),
            TariffWindowNextSwitchSensor(entry, coordinator),
            TariffWindowMinutesUntilActiveSensor(entry, coordinator),
            TariffWindowMinutesRemainingSensor(entry, coordinator),
        ]
    )


class TariffWindowSelectedWindowSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show the chosen tariff window as one block."""

    _attr_has_entity_name = True
    _attr_translation_key = "selected_window"

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_selected_window"

    @property
    def native_value(self) -> str | None:
        """Return selected window as a readable time range."""
        data = self.coordinator.data
        if data.selected_window_start is None or data.selected_window_end is None:
            return None
        return (
            f"{data.selected_window_start.strftime('%H:%M')} - "
            f"{data.selected_window_end.strftime('%H:%M')}"
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | None]:
        """Expose selected window details."""
        data = self.coordinator.data
        duration_hours = None
        if data.selected_window_start and data.selected_window_end:
            duration_hours = (
                data.selected_window_end - data.selected_window_start
            ).total_seconds() / 3600
        return {
            "start": data.selected_window_start.isoformat() if data.selected_window_start else None,
            "end": data.selected_window_end.isoformat() if data.selected_window_end else None,
            "hours": duration_hours,
            "total_price": round(data.selected_window_total_price, 6)
            if data.selected_window_total_price is not None
            else None,
        }


class TariffWindowNextSwitchSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show next moment when active state changes."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_switch"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_next_switch"

    @property
    def native_value(self):
        """Return next switch datetime."""
        return self.coordinator.data.next_switch


class TariffWindowMinutesUntilActiveSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show how many minutes remain until the next active window starts."""

    _attr_has_entity_name = True
    _attr_translation_key = "minutes_until_active"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_minutes_until_active"

    @property
    def native_value(self) -> int:
        """Return whole minutes until the active range starts."""
        return self.coordinator.data.minutes_until_active


class TariffWindowMinutesRemainingSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show how many minutes remain in the current active window."""

    _attr_has_entity_name = True
    _attr_translation_key = "minutes_remaining_active"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_minutes_remaining_active"

    @property
    def native_value(self) -> int:
        """Return whole minutes remaining in the current active range."""
        return self.coordinator.data.minutes_remaining_active
