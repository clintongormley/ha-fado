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

The exclude helper, which only exists in HA >= 2026.11.0, is covered here too.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.fado.const import DOMAIN
from custom_components.fado.ha_compat import (
    _extract_excluded_via_target,
    _extract_via_service,
    _extract_via_target,
    _has_exclude_helper,
    _has_target_selection,
    _no_excluded_entity_ids,
    extract_excluded_entity_ids,
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


def _make_exclude_call(hass: HomeAssistant, target: str, exclude: str) -> ServiceCall:
    """Build a fade_lights ServiceCall whose target has an exclude block."""
    return ServiceCall(
        hass, DOMAIN, "fade_lights", {"entity_id": target, "exclude": {"entity_id": exclude}}
    )


def test_no_exclude_helper_when_the_target_module_does_not_exist() -> None:
    """The oldest supported HA, 2025.2, has no ``helpers.target`` module."""
    with patch.dict(sys.modules, {"homeassistant.helpers.target": None}):
        assert not _has_exclude_helper()


def test_no_exclude_helper_when_the_target_module_lacks_it() -> None:
    """Later versions have the module without the helper, which arrived in 2026.11."""
    module = types.ModuleType("homeassistant.helpers.target")
    module.TargetSelection = object  # type: ignore[attr-defined]

    with patch.dict(sys.modules, {"homeassistant.helpers.target": module}):
        assert not _has_exclude_helper()


def test_excluded_ids_use_the_exclude_helper_when_present(hass: HomeAssistant) -> None:
    """The call's data is what the helper resolves (HA >= 2026.11.0)."""
    call = _make_exclude_call(hass, "light.test", "light.other")
    seen = []

    class FakeSelection:
        def __init__(self, config) -> None:
            seen.append(config)

    module = types.ModuleType("homeassistant.helpers.target")
    module.TargetSelection = FakeSelection  # type: ignore[attr-defined]
    module.async_extract_excluded_entity_ids = lambda _hass, selection: {  # type: ignore[attr-defined]
        "light.other"
    }

    with patch.dict(sys.modules, {"homeassistant.helpers.target": module}):
        assert _has_exclude_helper()
        assert _extract_excluded_via_target(hass, call) == {"light.other"}
    assert seen == [call.data]


def test_excluded_ids_are_empty_on_older_ha(hass: HomeAssistant) -> None:
    """The HA < 2026.11.0 fallback resolves nothing, whatever the call holds."""
    call = _make_exclude_call(hass, "light.test", "light.other")

    assert _no_excluded_entity_ids(hass, call) == set()


async def test_public_excluded_extractor_matches_the_running_ha(
    hass: HomeAssistant, mock_light_entity: str, mock_light_off: str
) -> None:
    """The selected public extractor resolves ``exclude`` only where HA supports it."""
    call = _make_exclude_call(hass, mock_light_entity, mock_light_off)

    expected = {mock_light_off} if _has_exclude_helper() else set()

    assert extract_excluded_entity_ids(hass, call) == expected
