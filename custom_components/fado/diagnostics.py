"""Diagnostics support for the Fado integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import FadeCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: FadeCoordinator | None = hass.data.get(DOMAIN)

    result: dict[str, Any] = {
        "config_entry": entry.as_dict(),
        "storage": {},
        "active_fades": [],
        "light_count": 0,
    }

    if coordinator is None:
        return result

    # Per-light storage data
    result["storage"] = dict(coordinator.data)

    # Active fades summary
    active_fades = []
    for entity_id, entity in coordinator._entities.items():
        if entity.is_fading or entity.expected_state:
            fade_info: dict[str, Any] = {
                "entity_id": entity_id,
                "is_fading": entity.is_fading,
                "is_restoring": entity.is_restoring,
            }
            if entity.expected_state:
                fade_info["expected_state_count"] = len(entity.expected_state.values)
            active_fades.append(fade_info)
    result["active_fades"] = active_fades

    # Count non-excluded lights
    result["light_count"] = sum(
        1
        for eid, config in coordinator.data.items()
        if isinstance(config, dict) and not config.get("exclude", False)
    )

    return result
