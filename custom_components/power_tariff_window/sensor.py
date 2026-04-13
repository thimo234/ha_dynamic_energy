"""Sensor platform for Power Tariff Window."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TariffWindowCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from config entry."""
    coordinator: TariffWindowCoordinator = entry.runtime_data
    async_add_entities([TariffWindowNextSwitchSensor(entry, coordinator)])


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
