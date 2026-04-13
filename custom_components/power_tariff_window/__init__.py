"""HA Dynamic Energy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_PRICE_SENSOR, DOMAIN, PLATFORMS
from .coordinator import TariffWindowCoordinator

type RuntimeData = TariffWindowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry."""
    coordinator = TariffWindowCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    price_sensor = entry.options.get(CONF_PRICE_SENSOR, entry.data.get(CONF_PRICE_SENSOR))
    if price_sensor:
        entry.async_on_unload(
            async_track_state_change_event(
                hass,
                [price_sensor],
                coordinator.async_handle_price_state_change,
            )
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
