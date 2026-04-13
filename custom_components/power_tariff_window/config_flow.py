"""Config flow for HA Dynamic Energy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

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
    DEFAULT_NAME,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
    MODE_CHEAPEST,
    MODE_EXPENSIVE,
)


def _schema_with_defaults(
    hass: HomeAssistant,
    defaults: dict[str, Any],
    current_price_sensor: str | None = None,
) -> vol.Schema:
    """Build config schema with only supported price sensors."""
    return vol.Schema(
        {
            vol.Required("name", default=defaults.get("name", DEFAULT_NAME)): selector.TextSelector(),
            vol.Required(
                CONF_PRICE_SENSOR,
                default=defaults.get(CONF_PRICE_SENSOR, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    include_entities=_compatible_price_sensor_ids(hass, current_price_sensor),
                )
            ),
            vol.Required(
                CONF_MODE,
                default=defaults.get(CONF_MODE, DEFAULT_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[MODE_CHEAPEST, MODE_EXPENSIVE],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="mode",
                )
            ),
            vol.Required(
                CONF_HOURS,
                default=defaults.get(CONF_HOURS, DEFAULT_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=24, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_WINDOW_START,
                default=defaults.get(CONF_WINDOW_START, DEFAULT_WINDOW_START),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_WINDOW_END,
                default=defaults.get(CONF_WINDOW_END, DEFAULT_WINDOW_END),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_ALIGN_TO_HOUR,
                default=defaults.get(CONF_ALIGN_TO_HOUR, DEFAULT_ALIGN_TO_HOUR),
            ): selector.BooleanSelector(),
        }
    )


class TariffWindowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial config step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title=user_input["name"], data=user_input)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_schema_with_defaults(
                self.hass,
                defaults,
                defaults.get(CONF_PRICE_SENSOR),
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow handler."""
        return TariffWindowOptionsFlowHandler(config_entry)


class TariffWindowOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle options for existing entries."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show and validate editable settings for an existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=user_input["name"],
                )
                return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema_with_defaults(
                self.hass,
                defaults,
                defaults.get(CONF_PRICE_SENSOR),
            ),
            errors=errors,
        )


def _validate(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    """Validate config flow input."""
    errors: dict[str, str] = {}

    try:
        hours = int(user_input[CONF_HOURS])
        if hours < 1 or hours > 24:
            errors["base"] = "invalid_hours"
    except (TypeError, ValueError):
        errors["base"] = "invalid_hours"

    price_sensor = user_input.get(CONF_PRICE_SENSOR)
    if not price_sensor:
        errors["base"] = "invalid_price_sensor"
        return errors

    state = hass.states.get(price_sensor)
    if state is None or not _is_compatible_price_sensor(state.attributes):
        errors["base"] = "invalid_price_sensor"

    return errors


def _compatible_price_sensor_ids(
    hass: HomeAssistant,
    current_price_sensor: str | None = None,
) -> list[str]:
    """Return compatible price sensor entity ids."""
    entity_ids = [
        state.entity_id
        for state in sorted(hass.states.async_all("sensor"), key=lambda item: item.name.lower())
        if _is_compatible_price_sensor(state.attributes)
    ]

    if current_price_sensor and current_price_sensor not in entity_ids:
        entity_ids.insert(0, current_price_sensor)

    return entity_ids


def _is_compatible_price_sensor(attributes: dict[str, Any]) -> bool:
    """Check if a sensor exposes price data we can consume."""
    return any(
        isinstance(attributes.get(key), list)
        for key in ("raw_today", "raw_tomorrow", "today", "tomorrow")
    )
