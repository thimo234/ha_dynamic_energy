"""Sensor platform for HA Dynamic Energy."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TariffWindowCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from config entry."""
    coordinator: TariffWindowCoordinator = entry.runtime_data
    async_add_entities(
        [
            TariffWindowSelectedWindowSensor(entry, coordinator),
            TariffWindowSelectedWindowStartSensor(entry, coordinator),
            TariffWindowSelectedWindowEndSensor(entry, coordinator),
            TariffWindowNextSwitchSensor(entry, coordinator),
            TariffWindowMinutesUntilActiveSensor(entry, coordinator),
            TariffWindowMinutesRemainingSensor(entry, coordinator),
        ]
    )


class TariffWindowSelectedWindowSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show the chosen tariff window as one block."""

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_selected_window"
        self._attr_name = f"{entry.title} Selected Window"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

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


class TariffWindowSelectedWindowStartSensor(
    CoordinatorEntity[TariffWindowCoordinator], SensorEntity
):
    """Show the start timestamp of the selected window."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_selected_window_start"
        self._attr_name = f"{entry.title} Selected Window Start"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

    @property
    def native_value(self):
        """Return selected window start."""
        return self.coordinator.data.selected_window_start


class TariffWindowSelectedWindowEndSensor(
    CoordinatorEntity[TariffWindowCoordinator], SensorEntity
):
    """Show the end timestamp of the selected window."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_selected_window_end"
        self._attr_name = f"{entry.title} Selected Window End"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

    @property
    def native_value(self):
        """Return selected window end."""
        return self.coordinator.data.selected_window_end


class TariffWindowNextSwitchSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show next moment when active state changes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_next_switch"
        self._attr_name = f"{entry.title} Next Switch Moment"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

    @property
    def native_value(self):
        """Return next switch datetime."""
        return self.coordinator.data.next_switch


class TariffWindowMinutesUntilActiveSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show how many minutes remain until the next active window starts."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_minutes_until_active"
        self._attr_name = f"{entry.title} Minutes Until Active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

    @property
    def native_value(self) -> int:
        """Return whole minutes until the active range starts."""
        return self.coordinator.data.minutes_until_active


class TariffWindowMinutesRemainingSensor(CoordinatorEntity[TariffWindowCoordinator], SensorEntity):
    """Show how many minutes remain in the current active window."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_minutes_remaining_active"
        self._attr_name = f"{entry.title} Minutes Remaining Active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

    @property
    def native_value(self) -> int:
        """Return whole minutes remaining in the current active range."""
        return self.coordinator.data.minutes_remaining_active
