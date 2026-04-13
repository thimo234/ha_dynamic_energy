"""Config flow for HA Dynamic Energy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_HOURS,
    CONF_MODE,
    CONF_PRICE_SENSOR,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    DEFAULT_HOURS,
    DEFAULT_MODE,
    DEFAULT_NAME,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
    MODE_CHEAPEST,
    MODE_EXPENSIVE,
)


def _schema_with_defaults(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "name",
                default=defaults.get("name", DEFAULT_NAME),
            ): selector.TextSelector(),
            vol.Required(
                CONF_PRICE_SENSOR,
                default=defaults.get(CONF_PRICE_SENSOR, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
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
        }
    )


class TariffWindowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                title = user_input["name"]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema_with_defaults({}),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return TariffWindowOptionsFlow(config_entry)


class TariffWindowOptionsFlow(config_entries.OptionsFlow):
    """Handle options for existing entry."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, title=user_input["name"]
                )
                return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema_with_defaults(defaults),
            errors=errors,
        )


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    try:
        hours = int(user_input[CONF_HOURS])
        if hours < 1 or hours > 24:
            errors["base"] = "invalid_hours"
    except (TypeError, ValueError):
        errors["base"] = "invalid_hours"
    return errors
