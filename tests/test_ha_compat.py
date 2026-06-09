"""Tests for the cross-version target-resolution compatibility shim.

`TargetSelection` (used by the modern resolution path) only exists in
HA >= 2026.1.0. On older HA the integration falls back to the long-standing
``homeassistant.helpers.service.async_extract_referenced_entity_ids`` helper,
which accepts a ``ServiceCall`` directly. These tests prove the fallback path
resolves targets identically to the modern path, so older HA versions are
genuinely supported.
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


def _make_call(hass: HomeAssistant, entity_id: str | list[str]) -> ServiceCall:
    """Build a fade_lights ServiceCall targeting the given entity id(s)."""
    return ServiceCall(hass, DOMAIN, "fade_lights", {"entity_id": entity_id})


def _resolved(selected) -> set[str]:
    """Flatten a SelectedEntities result to the referenced entity id set."""
    return selected.referenced | selected.indirectly_referenced


async def test_service_fallback_resolves_single_entity(
    hass: HomeAssistant, mock_light_entity: str
) -> None:
    """The HA < 2026.1.0 fallback resolves a single entity_id target."""
    call = _make_call(hass, mock_light_entity)

    selected = _extract_via_service(hass, call)

    assert mock_light_entity in _resolved(selected)


async def test_service_fallback_resolves_entity_list(
    hass: HomeAssistant, mock_light_entity: str, mock_light_off: str
) -> None:
    """The fallback resolves a list of entity_id targets."""
    call = _make_call(hass, [mock_light_entity, mock_light_off])

    selected = _extract_via_service(hass, call)

    assert {mock_light_entity, mock_light_off} <= _resolved(selected)


@pytest.mark.skipif(
    not _has_target_selection(),
    reason="homeassistant.helpers.target only exists on HA >= 2026.1.0",
)
async def test_target_and_service_paths_resolve_identically(
    hass: HomeAssistant, mock_light_entity: str, mock_light_off: str
) -> None:
    """Modern and fallback paths must resolve the same entity set."""
    call = _make_call(hass, [mock_light_entity, mock_light_off])

    assert _resolved(_extract_via_target(hass, call)) == _resolved(_extract_via_service(hass, call))


async def test_public_extractor_resolves_target(
    hass: HomeAssistant, mock_light_entity: str
) -> None:
    """The selected public extractor resolves targets on the running HA."""
    call = _make_call(hass, mock_light_entity)

    selected = extract_referenced_entity_ids(hass, call)

    assert mock_light_entity in _resolved(selected)
