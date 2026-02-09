"""Tests to cover specific code paths identified from coverage analysis."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_SUPPORTED_COLOR_MODES
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fado.const import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_FROM,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_XY_COLOR,
    DOMAIN,
    SERVICE_FADE_LIGHTS,
)
from custom_components.fado.expected_state import ExpectedValues
from custom_components.fado.fade_change import FadeChange
from custom_components.fado.fade_params import FadeParams


class TestNoFadeParameters:
    """Test early return when no fade parameters are specified (lines 171-172)."""

    async def test_no_fade_params_returns_early(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test service returns early when no fade parameters specified."""
        with patch(
            "custom_components.fado.coordinator.FadeCoordinator._fade_light",
            new_callable=AsyncMock,
        ) as mock_fade_light:
            # Call with only target, no brightness, colors, or from params
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    # No brightness_pct, no color params, no from params
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )
            await hass.async_block_till_done()

            # _fade_light should NOT be called since there's nothing to fade
            assert mock_fade_light.call_count == 0


class TestNonDimmableLightNoTarget:
    """Test non-dimmable light with no brightness target (line 610)."""

    def test_non_dimmable_no_brightness_target_returns_none(self) -> None:
        """Test FadeChange.resolve returns None for non-dimmable with no brightness target."""
        # State attributes for a non-dimmable light (ONOFF only)
        state_attributes = {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF],
            # No brightness attribute
        }

        # FadeParams with only color target, no brightness
        fade_params = FadeParams(
            brightness_pct=None,
            hs_color=(200.0, 80.0),  # Color target but no brightness
        )

        result = FadeChange.resolve(fade_params, state_attributes, 50)

        # Should return None because light can't dim and no brightness target
        assert result is None


class TestMiredsBoundaryFallback:
    """Test start_mireds boundary fallback logic (lines 733, 735)."""

    def test_only_min_mireds_available(self) -> None:
        """Test fallback to min_mireds when only min bound exists.

        When only max_color_temp_kelvin is available (no min), we only have
        min_mireds (from max kelvin). The code should use min_mireds as start.
        """
        # State with only max_color_temp_kelvin (gives us only min_mireds)
        state_attributes = {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
            ATTR_BRIGHTNESS: 200,
            "max_color_temp_kelvin": 6500,  # max kelvin = min mireds (~154)
            # No min_color_temp_kelvin - this means no max_mireds
        }

        # Target color temp with no starting color temp in state
        fade_params = FadeParams(
            color_temp_kelvin=4000,  # ~250 mireds
        )

        result = FadeChange.resolve(fade_params, state_attributes, 50)

        # Should return a FadeChange (not None)
        assert result is not None

    def test_only_max_mireds_available(self) -> None:
        """Test fallback to max_mireds when only max bound exists.

        When only min_color_temp_kelvin is available (no max), we only have
        max_mireds (from min kelvin). The code should use max_mireds as start.
        """
        # State with only min_color_temp_kelvin (gives us only max_mireds)
        state_attributes = {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
            ATTR_BRIGHTNESS: 200,
            "min_color_temp_kelvin": 2000,  # min kelvin = max mireds (500)
            # No max_color_temp_kelvin - this means no min_mireds
        }

        # Target color temp with no starting color temp in state
        fade_params = FadeParams(
            color_temp_kelvin=4000,  # ~250 mireds
        )

        result = FadeChange.resolve(fade_params, state_attributes, 50)

        # Should return a FadeChange (not None)
        assert result is not None


class TestExpectedValuesStr:
    """Test ExpectedValues __str__ method (lines 35-42)."""

    def test_str_with_brightness_only(self) -> None:
        """Test string representation with only brightness."""
        ev = ExpectedValues(brightness=128)
        result = str(ev)
        assert "brightness=128" in result
        assert "hs_color" not in result
        assert "color_temp_kelvin" not in result

    def test_str_with_hs_color_only(self) -> None:
        """Test string representation with only hs_color."""
        ev = ExpectedValues(hs_color=(200.0, 80.0))
        result = str(ev)
        assert "hs_color=(200.0, 80.0)" in result
        assert "brightness" not in result
        assert "color_temp_kelvin" not in result

    def test_str_with_color_temp_only(self) -> None:
        """Test string representation with only color_temp_kelvin."""
        ev = ExpectedValues(color_temp_kelvin=4000)
        result = str(ev)
        assert "color_temp_kelvin=4000" in result
        assert "brightness" not in result
        assert "hs_color" not in result

    def test_str_with_all_values(self) -> None:
        """Test string representation with all values."""
        ev = ExpectedValues(
            brightness=200,
            hs_color=(120.0, 50.0),
            color_temp_kelvin=3000,
        )
        result = str(ev)
        assert "brightness=200" in result
        assert "hs_color=(120.0, 50.0)" in result
        assert "color_temp_kelvin=3000" in result

    def test_str_empty(self) -> None:
        """Test string representation with no values."""
        ev = ExpectedValues()
        result = str(ev)
        assert "empty" in result


class TestSchemaValidation:
    """Test voluptuous schema validation for the fade_lights service."""

    async def test_rejects_unknown_top_level_parameter(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects unknown top-level parameters."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_BRIGHTNESS_PCT: 50,
                    "invalid_top_level_param": "value",
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_unknown_from_parameter(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects unknown parameters in from: block."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_BRIGHTNESS_PCT: 50,
                    ATTR_FROM: {
                        ATTR_BRIGHTNESS_PCT: 0,
                        "invalid_param": "value",
                    },
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_brightness_pct_out_of_range(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects brightness_pct above 100."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_BRIGHTNESS_PCT: 150,
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_rgbw_value_out_of_range(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects RGBW values outside 0-255."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_RGBW_COLOR: [100, 200, 300, 50],
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_rgbww_value_out_of_range(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects RGBWW values outside 0-255."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_RGBWW_COLOR: [100, 200, 50, 300, 50],
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_xy_value_out_of_range(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects XY values outside 0-1."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_XY_COLOR: [0.5, 1.5],
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_rgbw_negative_value(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects negative RGBW values."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_RGBW_COLOR: [-1, 200, 100, 50],
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_rgbww_negative_value(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects negative RGBWW values."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_RGBWW_COLOR: [100, -10, 50, 50, 50],
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )

    async def test_rejects_xy_negative_value(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        """Test schema rejects negative XY values."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                {
                    ATTR_XY_COLOR: [-0.1, 0.5],
                },
                target={"entity_id": mock_light_entity},
                blocking=True,
            )
