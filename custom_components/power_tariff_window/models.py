"""Data models for HA Dynamic Energy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class PriceSlot:
    """One priced time slot."""

    start: datetime
    end: datetime
    price: float


@dataclass(slots=True)
class TariffPlan:
    """Computed active plan."""

    active: bool
    next_switch: datetime | None
    selected_window_start: datetime | None
    selected_window_end: datetime | None
    selected_window_total_price: float | None
    next_active_start: datetime | None
    active_until: datetime | None
    minutes_until_active: int
    minutes_remaining_active: int
    selected_slots: list[PriceSlot]
