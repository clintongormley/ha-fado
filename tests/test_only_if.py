"""Tests for the only_if state filter on fado.fade_lights."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES
from homeassistant.components.light.const import ColorMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fado import FADE_LIGHTS_SCHEMA, _normalize_only_if
from custom_components.fado.const import ATTR_ONLY_IF, DOMAIN, SERVICE_FADE_LIGHTS
from custom_components.fado.fade_params import FadeParams


class TestNormalizeOnlyIf:
    """The standalone normalising validator."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("on", "on"),
            ("off", "off"),
            ("On", "on"),
            ("OFF", "off"),
            (True, "on"),  # YAML: `only_if: on` parses to True
            (False, "off"),  # YAML: `only_if: off` parses to False
        ],
    )
    def test_accepts_and_normalises(self, value: object, expected: str | None) -> None:
        assert _normalize_only_if(value) == expected

    @pytest.mark.parametrize("value", ["maybe", "", 5, [1], "onn"])
    def test_rejects_invalid(self, value: object) -> None:
        with pytest.raises(vol.Invalid):
            _normalize_only_if(value)


class TestSchemaWiring:
    """only_if normalised through the full service schema (needs a target)."""

    def test_schema_normalises_yaml_boolean(self) -> None:
        result = FADE_LIGHTS_SCHEMA(
            {ATTR_ENTITY_ID: "light.test", "brightness_pct": 50, ATTR_ONLY_IF: True}
        )
        assert result[ATTR_ONLY_IF] == "on"

    def test_schema_passes_null_through(self) -> None:
        result = FADE_LIGHTS_SCHEMA(
            {ATTR_ENTITY_ID: "light.test", "brightness_pct": 50, ATTR_ONLY_IF: None}
        )
        assert result[ATTR_ONLY_IF] is None

    def test_schema_rejects_junk(self) -> None:
        with pytest.raises(vol.Invalid):
            FADE_LIGHTS_SCHEMA(
                {ATTR_ENTITY_ID: "light.test", "brightness_pct": 50, ATTR_ONLY_IF: "maybe"}
            )


class TestFadeParamsOnlyIf:
    """only_if parsing on FadeParams."""

    def test_parses_only_if(self) -> None:
        params = FadeParams.from_service_data({"brightness_pct": 50, ATTR_ONLY_IF: "on"})
        assert params.only_if == "on"

    def test_absent_only_if_is_none(self) -> None:
        params = FadeParams.from_service_data({"brightness_pct": 50})
        assert params.only_if is None

    def test_explicit_null_only_if_is_none(self) -> None:
        params = FadeParams.from_service_data({"brightness_pct": 50, ATTR_ONLY_IF: None})
        assert params.only_if is None

    def test_only_if_does_not_count_as_target(self) -> None:
        # only_if alone is a filter, not a fade target — has_target must stay False.
        params = FadeParams.from_service_data({ATTR_ONLY_IF: "on"})
        assert params.only_if == "on"
        assert params.has_target() is False
        assert params.has_from_target() is False


class TestResolveTargetsOnlyIf:
    """_resolve_fade_targets honours only_if. Uses an end-to-end service call so
    the real targeting/expansion path runs."""

    async def _faded_entities(
        self, hass: HomeAssistant, target_ids: list[str], only_if: object
    ) -> set[str]:
        """Call fade_lights with the given target + only_if, return faded entity ids."""
        data: dict = {"brightness_pct": 50}
        if only_if is not None:
            data[ATTR_ONLY_IF] = only_if
        with patch(
            "custom_components.fado.coordinator.FadeCoordinator._fade_light",
            new_callable=AsyncMock,
        ) as mock_fade:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                data,
                target={"entity_id": target_ids},
                blocking=True,
            )
            await hass.async_block_till_done()
        return {c.args[0] for c in mock_fade.call_args_list}

    async def test_only_if_on_keeps_only_on_lights(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,  # on
        mock_light_off: str,  # off
    ) -> None:
        faded = await self._faded_entities(
            hass, [mock_light_entity, mock_light_off], "on"
        )
        assert faded == {mock_light_entity}

    async def test_only_if_off_keeps_only_off_lights(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
        mock_light_off: str,
    ) -> None:
        faded = await self._faded_entities(
            hass, [mock_light_entity, mock_light_off], "off"
        )
        assert faded == {mock_light_off}

    async def test_unset_only_if_keeps_all_lights(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
        mock_light_off: str,
    ) -> None:
        faded = await self._faded_entities(
            hass, [mock_light_entity, mock_light_off], None
        )
        assert faded == {mock_light_entity, mock_light_off}

    async def test_only_if_on_excludes_unknown_state(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        hass.states.async_set(
            "light.unknown_state",
            "unknown",
            {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
        )
        faded = await self._faded_entities(
            hass, [mock_light_entity, "light.unknown_state"], "on"
        )
        assert faded == {mock_light_entity}
