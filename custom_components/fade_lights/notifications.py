"""Notification helpers for unconfigured lights."""

from __future__ import annotations

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, REQUIRED_CONFIG_FIELDS


def _get_unconfigured_lights(hass: HomeAssistant) -> set[str]:
    """Return set of light entity_ids missing required configuration.

    A light is considered unconfigured if:
    - It is enabled (not disabled)
    - It is NOT excluded (exclude: true in storage)
    - It is missing any required config field (currently just min_delay_ms)
    """
    if DOMAIN not in hass.data:
        return set()

    entity_registry = er.async_get(hass)
    storage_data = hass.data[DOMAIN].get("data", {})

    unconfigured = set()
    for entry in entity_registry.entities.values():
        # Only check lights
        if entry.domain != LIGHT_DOMAIN:
            continue

        # Skip disabled lights
        if entry.disabled:
            continue

        entity_id = entry.entity_id
        config = storage_data.get(entity_id, {})

        # Skip excluded lights
        if config.get("exclude", False):
            continue

        # Check if any required field is missing
        if not REQUIRED_CONFIG_FIELDS.issubset(config.keys()):
            unconfigured.add(entity_id)

    return unconfigured
