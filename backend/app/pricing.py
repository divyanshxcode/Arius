"""Pricing engine.

    rate($/s) = (host list price / 3600) * (1 + queue_pressure) * tier_multiplier

queue_pressure = queued_jobs / max(free_slices, 1), capped at 1.5 so the
meter never goes absurd during a burst.

Tier multipliers mirror the product story: confidential capacity costs more
because it requires datacenter cards with hardware isolation.
"""

from __future__ import annotations

TIER_PRIORITY = {"plain": 0, "vgpu": 1, "confidential": 2}
TIER_MULTIPLIER = {"plain": 1.0, "vgpu": 1.2, "confidential": 1.8}

MAX_PRESSURE = 1.5


def queue_pressure(queued: int, free_slices: int) -> float:
    return min(MAX_PRESSURE, queued / max(free_slices, 1))


def per_second_rate(price_per_hour: float, tier: str, pressure: float) -> float:
    base = max(price_per_hour, 0.0) / 3600.0
    return round(base * (1.0 + pressure) * TIER_MULTIPLIER.get(tier, 1.0), 8)


def tier_allows(host_tier: str, required_tier: str) -> bool:
    return TIER_PRIORITY.get(host_tier, -1) >= TIER_PRIORITY.get(required_tier, 99)
