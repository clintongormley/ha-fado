"""Tests for the ``exclude`` block of a fade_lights target (HA >= 2026.11).

An excluded light must never fade, even when a light group reaches it. Home
Assistant only removes excluded entities from the resolved target, so a group
left in the target would bring its excluded members back during group expansion.

The expansion tests pass an explicit ``excluded`` set and run on every supported
HA version. The end-to-end tests need HA's own exclude support and are skipped
without it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_SUPPORTED_COLOR_MODES
from homeassistant.components.light.const import ColorMode
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_call_from_config
from homeassistant.setup import async_setup_component

from custom_components.fado.const import DOMAIN, SERVICE_FADE_LIGHTS
from custom_components.fado.coordinator import FadeCoordinator
from custom_components.fado.ha_compat import _has_exclude_helper
from tests.ha_harness import MockConfigEntry

_HAS_EXCLUDE_HELPER = _has_exclude_helper()

requires_exclude = pytest.mark.skipif(
    not _HAS_EXCLUDE_HELPER,
    reason="homeassistant.helpers.target.async_extract_excluded_entity_ids "
    "only exists on HA >= 2026.11.0",
)

LIGHT_ATTRIBUTES = {
    ATTR_BRIGHTNESS: 200,
    ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
}

GROUPS = {
    "g": ["light.a", "light.b"],
    "n": ["light.x"],
    "p": ["light.n", "light.y"],
    "p_with_x": ["light.n", "light.x", "light.y"],
}


def _set_lights(hass: HomeAssistant) -> None:
    for name in "abxy":
        hass.states.async_set(f"light.{name}", STATE_ON, LIGHT_ATTRIBUTES)


class TestExpandLightGroupsWithExcluded:
    """The group walk, given the excluded set directly."""

    @pytest.fixture
    def coordinator(
        self, hass: HomeAssistant, init_integration: MockConfigEntry
    ) -> FadeCoordinator:
        _set_lights(hass)
        for name, members in GROUPS.items():
            hass.states.async_set(
                f"light.{name}",
                STATE_ON,
                {**LIGHT_ATTRIBUTES, ATTR_ENTITY_ID: members},
            )
        return hass.data[DOMAIN]

    @pytest.mark.parametrize(
        ("targets", "excluded", "expected"),
        [
            pytest.param(["light.g"], {"light.a"}, {"light.b"}, id="member_of_targeted_group"),
            pytest.param(
                ["light.a", "light.b", "light.g"],
                {"light.a"},
                {"light.b"},
                id="member_of_group_in_targeted_area",
            ),
            pytest.param(["light.p"], {"light.n"}, {"light.y"}, id="nested_group"),
            pytest.param(
                ["light.p_with_x"],
                {"light.n"},
                {"light.x", "light.y"},
                id="nested_group_whose_member_is_also_direct",
            ),
            pytest.param(
                ["light.a", "light.b", "light.g"],
                {"light.g"},
                {"light.a", "light.b"},
                id="group_in_targeted_area",
            ),
            pytest.param(["light.g"], {"light.a", "light.b"}, set(), id="every_member"),
        ],
    )
    def test_excluded_entities_are_skipped_during_the_walk(
        self,
        coordinator: FadeCoordinator,
        targets: list[str],
        excluded: set[str],
        expected: set[str],
    ) -> None:
        assert set(coordinator._expand_light_groups(targets, excluded=excluded)) == expected

    def test_nothing_excluded_by_default(self, coordinator: FadeCoordinator) -> None:
        assert set(coordinator._expand_light_groups(["light.g"])) == {"light.a", "light.b"}


@requires_exclude
class TestFadeLightsTargetExclude:
    """A real target through HA's validation and target resolution."""

    @pytest.fixture
    async def room(self, hass: HomeAssistant, init_integration: MockConfigEntry) -> str:
        """Set up real groups, and an area holding a, b and g. Returns the area id."""
        area = ar.async_get(hass).async_create("room")
        registry = er.async_get(hass)
        for name in "ab":
            entry = registry.async_get_or_create("light", "test", name, suggested_object_id=name)
            registry.async_update_entity(entry.entity_id, area_id=area.id)
        _set_lights(hass)

        # Must precede the light setup, which loads the group component without this config.
        assert await async_setup_component(
            hass, "group", {"group": {"x": {"entities": ["light.a"]}}}
        )
        assert await async_setup_component(
            hass,
            "light",
            {
                "light": [
                    {"platform": "group", "name": name, "unique_id": name, "entities": members}
                    for name, members in GROUPS.items()
                ]
            },
        )
        await hass.async_block_till_done()

        registry.async_update_entity("light.g", area_id=area.id)
        await hass.async_block_till_done()
        return area.id

    @staticmethod
    async def _faded(hass: HomeAssistant, target: dict) -> set[str]:
        with patch.object(FadeCoordinator, "_fade_light", new_callable=AsyncMock) as fade:
            await async_call_from_config(
                hass,
                {
                    "action": f"{DOMAIN}.{SERVICE_FADE_LIGHTS}",
                    "target": target,
                    "data": {"brightness_pct": 50},
                },
                blocking=True,
                validate_config=True,
            )
            await hass.async_block_till_done()
        return {call.args[0] for call in fade.call_args_list}

    @pytest.mark.parametrize(
        ("target", "exclude", "expected"),
        [
            pytest.param({"entity_id": "light.g"}, "light.a", {"light.b"}, id="group_minus_member"),
            pytest.param({}, "light.a", {"light.b"}, id="area_minus_member_of_its_group"),
            pytest.param({"entity_id": "light.p"}, "light.n", {"light.y"}, id="nested_group"),
            pytest.param(
                {"entity_id": "light.p_with_x"},
                "light.n",
                {"light.x", "light.y"},
                id="nested_group_whose_member_is_also_direct",
            ),
            pytest.param({}, "light.g", {"light.a", "light.b"}, id="area_minus_group"),
            pytest.param(
                {"entity_id": "light.g"}, ["light.a", "light.b"], set(), id="every_member"
            ),
        ],
    )
    async def test_excluded_lights_do_not_fade(
        self,
        hass: HomeAssistant,
        room: str,
        target: dict,
        exclude: str | list[str],
        expected: set[str],
    ) -> None:
        selection = {**(target or {"area_id": room}), "exclude": {"entity_id": exclude}}

        assert await self._faded(hass, selection) == expected

    @pytest.mark.parametrize(
        "target",
        [
            pytest.param({"entity_id": ["light.a", "light.b"]}, id="direct_lights"),
            pytest.param({"entity_id": "light.g"}, id="light_group"),
            pytest.param({}, id="area"),
        ],
    )
    async def test_old_style_group_in_exclude_hides_its_members(
        self, hass: HomeAssistant, room: str, target: dict
    ) -> None:
        selection = {**(target or {"area_id": room}), "exclude": {"entity_id": "group.x"}}

        assert await self._faded(hass, selection) == {"light.b"}
