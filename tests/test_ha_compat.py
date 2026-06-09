"""Tests for the cross-version target-resolution compatibility shim.

The ``TargetSelection`` symbol (used by the modern resolution path) only exists
in HA >= 2026.1.0. On older HA the integration falls back to the long-standing
``homeassistant.helpers.service.async_extract_referenced_entity_ids`` helper,
which accepts a ``ServiceCall`` directly. These tests prove the fallback path
resolves targets identically to the modern path, so older HA versions are
genuinely supported.

The tests that call ``_extract_via_service`` directly are skipped once that
legacy helper is removed (HA 2026.8): there the integration uses the modern
path, so the fallback is no longer reachable. The min-version CI leg still
exercises it.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.fado.const import DOMAIN
from custom_components.fado.ha_compat import (
    _extract_via_service,
    _extract_via_target,
    _has_target_selection,
    extract_referenced_entity_ids,
)


def _has_legacy_service_extractor() -> bool:
    """Whether the legacy service helper still exists (removed in HA 2026.8)."""
    from homeassistant.helpers import service

    return hasattr(service, "async_extract_referenced_entity_ids")


_HAS_LEGACY_SERVICE = _has_legacy_service_extractor()
_HAS_TARGET_SELECTION = _has_target_selection()

requires_legacy_service = pytest.mark.skipif(
    not _HAS_LEGACY_SERVICE,
    reason="homeassistant.helpers.service.async_extract_referenced_entity_ids removed in HA 2026.8",
)
requires_target_selection = pytest.mark.skipif(
    not _HAS_TARGET_SELECTION,
    reason="homeassistant.helpers.target.TargetSelection only exists on HA >= 2026.1.0",
)


def _make_call(hass: HomeAssistant, entity_id: str | list[str]) -> ServiceCall:
    """Build a fade_lights ServiceCall targeting the given entity id(s)."""
    return ServiceCall(hass, DOMAIN, "fade_lights", {"entity_id": entity_id})


def _resolved(selected) -> set[str]:
    """Flatten a SelectedEntities result to the referenced entity id set."""
    return selected.referenced | selected.indirectly_referenced


@requires_legacy_service
async def test_service_fallback_resolves_single_entity(
    hass: HomeAssistant, mock_light_entity: str
) -> None:
    """The HA < 2026.1.0 fallback resolves a single entity_id target."""
    call = _make_call(hass, mock_light_entity)

    selected = _extract_via_service(hass, call)

    assert mock_light_entity in _resolved(selected)


@requires_legacy_service
async def test_service_fallback_resolves_entity_list(
    hass: HomeAssistant, mock_light_entity: str, mock_light_off: str
) -> None:
    """The fallback resolves a list of entity_id targets."""
    call = _make_call(hass, [mock_light_entity, mock_light_off])

    selected = _extract_via_service(hass, call)

    assert {mock_light_entity, mock_light_off} <= _resolved(selected)


@requires_target_selection
@requires_legacy_service
async def test_target_and_service_paths_resolve_identically(
    hass: HomeAssistant, mock_light_entity: str, mock_light_off: str
) -> None:
    """Modern and fallback paths must resolve the same entity set.

    Only meaningful where both paths exist (2026.1.0 <= HA < 2026.8).
    """
    call = _make_call(hass, [mock_light_entity, mock_light_off])

    assert _resolved(_extract_via_target(hass, call)) == _resolved(_extract_via_service(hass, call))


async def test_public_extractor_resolves_target(
    hass: HomeAssistant, mock_light_entity: str
) -> None:
    """The selected public extractor resolves targets on the running HA."""
    call = _make_call(hass, mock_light_entity)

    selected = extract_referenced_entity_ids(hass, call)

    assert mock_light_entity in _resolved(selected)
