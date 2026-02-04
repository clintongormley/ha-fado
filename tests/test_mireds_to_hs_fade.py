"""Integration tests for mireds-to-HS hybrid fade transitions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light.const import ColorMode
from homeassistant.const import STATE_ON

from custom_components.fade_lights import _execute_fade
from custom_components.fade_lights.models import FadeParams, FadeStep


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.data = {
        "fade_lights": {
            "data": {},
            "store": MagicMock(),
            "min_step_delay_ms": 100,
        }
    }
    return hass


@pytest.fixture
def color_temp_light_state():
    """Create a light state in COLOR_TEMP mode."""
    state = MagicMock()
    state.state = STATE_ON
    state.attributes = {
        "brightness": 200,
        "color_mode": ColorMode.COLOR_TEMP,
        "color_temp": 333,  # ~3000K in mireds
        "supported_color_modes": [ColorMode.COLOR_TEMP, ColorMode.HS],
    }
    return state


class TestMiredsToHsFade:
    """Integration tests for mireds-to-HS transitions."""

    @pytest.mark.asyncio
    async def test_color_temp_to_hs_uses_hybrid_fade(
        self, mock_hass, color_temp_light_state
    ):
        """Test that COLOR_TEMP mode light fading to HS uses hybrid transition."""
        mock_hass.states.get = MagicMock(return_value=color_temp_light_state)

        cancel_event = asyncio.Event()

        fade_params = FadeParams(
            brightness_pct=None,
            hs_color=(0.0, 100.0),  # Red
        )

        with patch(
            "custom_components.fade_lights._build_mireds_to_hs_steps"
        ) as mock_builder, patch(
            "custom_components.fade_lights._save_storage", new_callable=AsyncMock
        ):
            mock_builder.return_value = [
                FadeStep(color_temp_mireds=300),
                FadeStep(hs_color=(30.0, 20.0)),
                FadeStep(hs_color=(0.0, 100.0)),
            ]

            await _execute_fade(
                mock_hass,
                "light.test",
                fade_params,
                transition_ms=3000,
                min_step_delay_ms=100,
                cancel_event=cancel_event,
            )

            # Verify hybrid builder was called
            mock_builder.assert_called_once()
            call_args = mock_builder.call_args
            assert call_args[0][0] == 333  # start_mireds
            assert call_args[0][1] == (0.0, 100.0)  # end_hs

    @pytest.mark.asyncio
    async def test_hs_mode_light_does_not_use_hybrid(self, mock_hass):
        """Test that HS mode light uses standard fade, not hybrid."""
        hs_state = MagicMock()
        hs_state.state = STATE_ON
        hs_state.attributes = {
            "brightness": 200,
            "color_mode": ColorMode.HS,
            "hs_color": (200.0, 50.0),
            "supported_color_modes": [ColorMode.COLOR_TEMP, ColorMode.HS],
        }
        mock_hass.states.get = MagicMock(return_value=hs_state)

        cancel_event = asyncio.Event()

        fade_params = FadeParams(
            brightness_pct=None,
            hs_color=(0.0, 100.0),
        )

        with patch(
            "custom_components.fade_lights._build_mireds_to_hs_steps"
        ) as mock_hybrid, patch(
            "custom_components.fade_lights._build_fade_steps"
        ) as mock_standard, patch(
            "custom_components.fade_lights._save_storage", new_callable=AsyncMock
        ):
            mock_standard.return_value = [FadeStep(hs_color=(0.0, 100.0))]

            await _execute_fade(
                mock_hass,
                "light.test",
                fade_params,
                transition_ms=3000,
                min_step_delay_ms=100,
                cancel_event=cancel_event,
            )

            # Hybrid should NOT be called
            mock_hybrid.assert_not_called()

    @pytest.mark.asyncio
    async def test_color_temp_to_mireds_uses_standard_fade(
        self, mock_hass, color_temp_light_state
    ):
        """Test that COLOR_TEMP to mireds uses standard fade (no mode switch needed)."""
        mock_hass.states.get = MagicMock(return_value=color_temp_light_state)

        cancel_event = asyncio.Event()

        fade_params = FadeParams(
            brightness_pct=None,
            color_temp_mireds=200,  # Target is mireds, not HS
        )

        with patch(
            "custom_components.fade_lights._build_mireds_to_hs_steps"
        ) as mock_hybrid, patch(
            "custom_components.fade_lights._save_storage", new_callable=AsyncMock
        ):
            await _execute_fade(
                mock_hass,
                "light.test",
                fade_params,
                transition_ms=3000,
                min_step_delay_ms=100,
                cancel_event=cancel_event,
            )

            # Hybrid should NOT be called (staying in mireds mode)
            mock_hybrid.assert_not_called()
