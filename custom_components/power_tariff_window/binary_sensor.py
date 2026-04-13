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
        slots = [
            {
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "price": slot.price,
            }
            for slot in self.coordinator.data.selected_slots
        ]
        if slots:
            selected_window = {
                "start": slots[0]["start"],
                "end": slots[-1]["end"],
                "hours": len(slots),
                "total_price": round(sum(slot["price"] for slot in slots), 6),
            }
        else:
            selected_window = None
        return {
            "selected_slots": slots,
            "selected_window": selected_window,
        }
