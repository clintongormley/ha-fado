"""Cross-version compatibility helpers.

Isolates Home Assistant APIs that differ across the supported version range so
the rest of the integration can stay version-agnostic.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall


def _extract_via_target(hass: HomeAssistant, call: ServiceCall):
    """Resolve referenced entities using the modern target helper (HA >= 2026.1.0)."""
    from homeassistant.helpers.target import (  # noqa: PLC0415
        TargetSelection,
        async_extract_referenced_entity_ids,
    )

    return async_extract_referenced_entity_ids(hass, TargetSelection(call.data))


def _extract_via_service(hass: HomeAssistant, call: ServiceCall):
    """Resolve referenced entities using the legacy service helper (HA < 2026.1.0).

    ``homeassistant.helpers.service.async_extract_referenced_entity_ids`` accepts
    a ``ServiceCall`` directly and predates the ``target`` helper. It is
    deprecated on newer HA (removed in 2026.8), but this path only runs on older
    HA where it remains the canonical API.
    """
    from homeassistant.helpers.service import (  # noqa: PLC0415
        async_extract_referenced_entity_ids,
    )

    return async_extract_referenced_entity_ids(hass, call)


def _has_target_selection() -> bool:
    """Return True if the modern ``TargetSelection`` API is available."""
    try:
        from homeassistant.helpers.target import TargetSelection  # noqa: F401, PLC0415
    except ImportError:  # pragma: no cover - only on HA < 2026.1.0
        return False
    return True


# Select the resolution strategy once, at import time, based on the running HA.
if _has_target_selection():
    extract_referenced_entity_ids = _extract_via_target
else:  # pragma: no cover - exercised only on HA < 2026.1.0
    extract_referenced_entity_ids = _extract_via_service
