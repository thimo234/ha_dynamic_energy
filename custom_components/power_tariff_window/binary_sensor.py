"""Binary sensor platform for HA Dynamic Energy."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TariffWindowCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor from config entry."""
    coordinator: TariffWindowCoordinator = entry.runtime_data
    async_add_entities([TariffWindowActiveBinarySensor(entry, coordinator)])


class TariffWindowActiveBinarySensor(CoordinatorEntity[TariffWindowCoordinator], BinarySensorEntity):
    """True while current hour is one of selected cheapest/expensive slots."""

    _attr_has_entity_name = True
    _attr_translation_key = "active"

    def __init__(self, entry: ConfigEntry, coordinator: TariffWindowCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Custom",
            "model": "Tariff Window Planner",
        }

    @property
    def is_on(self) -> bool:
        """Return true when configured slot is active."""
        return self.coordinator.data.active

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the selected block for dashboard usage."""
        data = self.coordinator.data
        if data.selected_window_start and data.selected_window_end:
            duration_hours = (
                data.selected_window_end - data.selected_window_start
            ).total_seconds() / 3600
            return {
                "selected_window_start": data.selected_window_start.isoformat(),
                "selected_window_end": data.selected_window_end.isoformat(),
                "selected_window_hours": duration_hours,
                "selected_window_total_price": round(data.selected_window_total_price or 0, 6),
            }
        return {"selected_window": None}
