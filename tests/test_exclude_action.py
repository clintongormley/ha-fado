"""Tests for fado.exclude_lights and fado.include_lights services."""

from __future__ import annotations

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_SUPPORTED_COLOR_MODES
from homeassistant.components.light.const import ColorMode
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fado.const import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
    DOMAIN,
    EVENT_CONFIG_UPDATED,
    SERVICE_EXCLUDE_LIGHTS,
    SERVICE_FADE_LIGHTS,
    SERVICE_INCLUDE_LIGHTS,
)


@pytest.fixture
def two_lights(hass: HomeAssistant) -> tuple[str, str]:
    """Create two dimmable lights at brightness 200."""
    for eid in ("light.living_room", "light.bedroom"):
        hass.states.async_set(
            eid,
            STATE_ON,
            {ATTR_BRIGHTNESS: 200, ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
        )
    return ("light.living_room", "light.bedroom")


async def test_exclude_sets_flag(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
) -> None:
    """Test exclude_lights sets exclude=True in storage."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    config = hass.data[DOMAIN].data.get("light.living_room", {})
    assert config.get("exclude") is True


async def test_include_clears_flag(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
) -> None:
    """Test include_lights sets exclude=False in storage."""
    # Pre-exclude the light
    hass.data[DOMAIN].data["light.living_room"] = {"exclude": True}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    config = hass.data[DOMAIN].data["light.living_room"]
    assert config.get("exclude") is False


async def test_exclude_multiple_targets(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
) -> None:
    """Test exclude_lights works with multiple entity targets."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LIGHTS,
        {},
        target={"entity_id": list(two_lights)},
        blocking=True,
    )
    await hass.async_block_till_done()

    for eid in two_lights:
        assert hass.data[DOMAIN].data[eid].get("exclude") is True


async def test_exclude_persists_to_store(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
) -> None:
    """Test that exclude_lights persists to the store."""
    store = hass.data[DOMAIN].store

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    store.async_save.assert_called()


async def test_excluded_light_skipped_by_fade(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
    captured_calls: list,
) -> None:
    """Test that an excluded light is skipped when fade_lights is called."""
    # Exclude one light
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fade both lights
    await hass.services.async_call(
        DOMAIN,
        SERVICE_FADE_LIGHTS,
        {ATTR_BRIGHTNESS_PCT: 50, ATTR_TRANSITION: 0.1},
        target={"entity_id": list(two_lights)},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Only bedroom should have been faded
    called_entities = {c.data.get("entity_id") for c in captured_calls}
    assert "light.bedroom" in called_entities
    assert "light.living_room" not in called_entities

    # Verify brightness: excluded unchanged, included changed
    assert hass.states.get("light.living_room").attributes[ATTR_BRIGHTNESS] == 200
    assert hass.states.get("light.bedroom").attributes[ATTR_BRIGHTNESS] == 127


async def test_include_then_fade_works(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
    captured_calls: list,
) -> None:
    """Test that re-including a light makes it respond to fade_lights."""
    # Exclude then re-include
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Fade the light
    await hass.services.async_call(
        DOMAIN,
        SERVICE_FADE_LIGHTS,
        {ATTR_BRIGHTNESS_PCT: 50, ATTR_TRANSITION: 0.1},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Light should have been faded
    assert hass.states.get("light.living_room").attributes[ATTR_BRIGHTNESS] == 127


async def test_exclude_fires_config_updated_event(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    two_lights: tuple[str, str],
) -> None:
    """Test that exclude/include services fire a config updated event for the panel."""
    events: list = []
    hass.bus.async_listen(EVENT_CONFIG_UPDATED, lambda e: events.append(e))

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EXCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INCLUDE_LIGHTS,
        {},
        target={"entity_id": "light.living_room"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(events) == 2


async def test_services_unloaded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that exclude/include services are removed on unload."""
    # Services should exist after setup
    assert hass.services.has_service(DOMAIN, SERVICE_EXCLUDE_LIGHTS)
    assert hass.services.has_service(DOMAIN, SERVICE_INCLUDE_LIGHTS)

    # Unload the entry
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    # Services should be gone
    assert not hass.services.has_service(DOMAIN, SERVICE_EXCLUDE_LIGHTS)
    assert not hass.services.has_service(DOMAIN, SERVICE_INCLUDE_LIGHTS)
