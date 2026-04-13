# HA Dynamic Energy

Custom Home Assistant integration to find the cheapest or most expensive contiguous block of `x` hours inside a configurable time window based on an existing price sensor such as Nord Pool.

## Features

- UI configuration flow (no YAML required)
- Select your existing price sensor entity
- Choose `cheapest` or `most expensive`
- Set number of hours (`x`) for one contiguous slot
- Set a daily search window (`start` and `end`)
- Binary sensor becomes `on` when the current time falls inside the selected block
- Timestamp sensor shows the next switch moment
- Installable through HACS as a custom repository

## Installation (HACS)

1. Push this repository to GitHub.
2. In Home Assistant, open HACS.
3. Add this repo as a custom repository (category: Integration).
4. Install **HA Dynamic Energy**.
5. Restart Home Assistant.
6. Go to **Settings > Devices & Services > Add Integration**.
7. Add **HA Dynamic Energy** and configure your window.

## Multiple moments

Create multiple integration entries if you want multiple schedules (for example one for cheapest night charging and one for most expensive peak hours).

## Created entities

- `binary_sensor.<name>_active`
  - `on` when current time is inside the selected block
  - includes `selected_slots` and `selected_window` attributes
- `sensor.<name>_next_switch_moment`
  - next timestamp where active state changes

## Notes

- The integration reads hourly prices from sensor attributes:
  - preferred: `raw_today` / `raw_tomorrow`
  - fallback: `today` / `tomorrow`
- If your source does not expose these attributes, no selection can be made.
