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
