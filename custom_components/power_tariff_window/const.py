"""Constants for the HA Dynamic Energy integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "power_tariff_window"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_PRICE_SENSOR = "price_sensor"
CONF_MODE = "mode"
CONF_HOURS = "hours"
CONF_WINDOW_START = "window_start"
CONF_WINDOW_END = "window_end"
CONF_ALIGN_TO_HOUR = "align_to_hour"

MODE_CHEAPEST = "cheapest"
MODE_EXPENSIVE = "expensive"

DEFAULT_NAME = "HA Dynamic Energy"
DEFAULT_HOURS = 1
DEFAULT_MODE = MODE_CHEAPEST
DEFAULT_WINDOW_START = "00:00:00"
DEFAULT_WINDOW_END = "23:59:00"
DEFAULT_ALIGN_TO_HOUR = True
