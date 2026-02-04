"""Tests for resolver helper functions."""

from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.light import ATTR_HS_COLOR as HA_ATTR_HS_COLOR

from custom_components.fade_lights import (
    _resolve_end_brightness,
    _resolve_start_brightness,
    _resolve_start_hs,
    _resolve_start_mireds,
)
from custom_components.fade_lights.fade_params import FadeParams


class TestResolveStartBrightness:
    """Test _resolve_start_brightness function."""

    def test_uses_from_brightness_pct_when_specified(self) -> None:
        """Test that from_brightness_pct takes precedence over state."""
        params = FadeParams(from_brightness_pct=50)
        state = {ATTR_BRIGHTNESS: 200}

        result = _resolve_start_brightness(params, state)

        # 50% of 255 = 127.5, truncated to 127
        assert result == 127

    def test_uses_current_state_when_no_from_brightness(self) -> None:
        """Test that current state is used when from_brightness_pct is None."""
        params = FadeParams()
        state = {ATTR_BRIGHTNESS: 180}

        result = _resolve_start_brightness(params, state)

        assert result == 180

    def test_returns_zero_when_both_missing(self) -> None:
        """Test that 0 is returned when neither source has brightness (light off)."""
        params = FadeParams()
        state = {}

        result = _resolve_start_brightness(params, state)

        # When light is off (no brightness in state), treat as 0
        assert result == 0

    def test_from_brightness_pct_zero(self) -> None:
        """Test handling of 0% brightness."""
        params = FadeParams(from_brightness_pct=0)
        state = {ATTR_BRIGHTNESS: 255}

        result = _resolve_start_brightness(params, state)

        assert result == 0

    def test_from_brightness_pct_100(self) -> None:
        """Test handling of 100% brightness."""
        params = FadeParams(from_brightness_pct=100)
        state = {ATTR_BRIGHTNESS: 50}

        result = _resolve_start_brightness(params, state)

        assert result == 255

    def test_state_brightness_none(self) -> None:
        """Test handling of None brightness in state (light off)."""
        params = FadeParams()
        state = {ATTR_BRIGHTNESS: None}

        result = _resolve_start_brightness(params, state)

        # When light is off (brightness is None), treat as 0
        assert result == 0


class TestResolveEndBrightness:
    """Test _resolve_end_brightness function."""

    def test_uses_brightness_pct_when_specified(self) -> None:
        """Test that brightness_pct is converted to 0-255 scale."""
        params = FadeParams(brightness_pct=75)
        state = {ATTR_BRIGHTNESS: 100}

        result = _resolve_end_brightness(params, state)

        # 75% of 255 = 191.25, truncated to 191
        assert result == 191

    def test_returns_none_when_not_specified(self) -> None:
        """Test that None is returned when brightness_pct is not set."""
        params = FadeParams()
        state = {ATTR_BRIGHTNESS: 200}

        result = _resolve_end_brightness(params, state)

        assert result is None

    def test_brightness_pct_zero(self) -> None:
        """Test handling of 0% end brightness."""
        params = FadeParams(brightness_pct=0)
        state = {}

        result = _resolve_end_brightness(params, state)

        assert result == 0

    def test_brightness_pct_100(self) -> None:
        """Test handling of 100% end brightness."""
        params = FadeParams(brightness_pct=100)
        state = {}

        result = _resolve_end_brightness(params, state)

        assert result == 255

    def test_state_ignored(self) -> None:
        """Test that state is ignored for end brightness (unlike start)."""
        params = FadeParams()
        state = {ATTR_BRIGHTNESS: 255}

        result = _resolve_end_brightness(params, state)

        # Should return None, not the state value
        assert result is None


class TestResolveStartHs:
    """Test _resolve_start_hs function."""

    def test_uses_from_hs_color_when_specified(self) -> None:
        """Test that from_hs_color takes precedence over state."""
        params = FadeParams(from_hs_color=(120.0, 80.0))
        state = {HA_ATTR_HS_COLOR: (240.0, 50.0)}

        result = _resolve_start_hs(params, state)

        assert result == (120.0, 80.0)

    def test_uses_current_state_when_no_from_hs(self) -> None:
        """Test that current state is used when from_hs_color is None."""
        params = FadeParams()
        state = {HA_ATTR_HS_COLOR: (30.0, 100.0)}

        result = _resolve_start_hs(params, state)

        assert result == (30.0, 100.0)

    def test_returns_none_when_both_missing(self) -> None:
        """Test that None is returned when neither source has HS color."""
        params = FadeParams()
        state = {}

        result = _resolve_start_hs(params, state)

        assert result is None

    def test_edge_case_hue_zero(self) -> None:
        """Test handling of hue=0 (red)."""
        params = FadeParams(from_hs_color=(0.0, 100.0))
        state = {}

        result = _resolve_start_hs(params, state)

        assert result == (0.0, 100.0)

    def test_edge_case_saturation_zero(self) -> None:
        """Test handling of saturation=0 (white)."""
        params = FadeParams(from_hs_color=(180.0, 0.0))
        state = {}

        result = _resolve_start_hs(params, state)

        assert result == (180.0, 0.0)

    def test_state_returns_list_converted_to_tuple(self) -> None:
        """Test that list from state is returned as-is (caller handles conversion)."""
        # Note: The resolver returns the raw state value; conversion to tuple
        # happens elsewhere if needed
        params = FadeParams()
        state = {HA_ATTR_HS_COLOR: [60.0, 75.0]}

        result = _resolve_start_hs(params, state)

        # Returns the list as-is
        assert result == [60.0, 75.0]


class TestResolveStartMireds:
    """Test _resolve_start_mireds function."""

    def test_uses_from_color_temp_mireds_when_specified(self) -> None:
        """Test that from_color_temp_mireds takes precedence over state."""
        params = FadeParams(from_color_temp_mireds=250)
        state = {"color_temp": 400}

        result = _resolve_start_mireds(params, state)

        assert result == 250

    def test_uses_current_state_when_no_from_mireds(self) -> None:
        """Test that current state is used when from_color_temp_mireds is None."""
        params = FadeParams()
        state = {"color_temp": 333}

        result = _resolve_start_mireds(params, state)

        assert result == 333

    def test_returns_none_when_both_missing(self) -> None:
        """Test that None is returned when neither source has mireds."""
        params = FadeParams()
        state = {}

        result = _resolve_start_mireds(params, state)

        assert result is None

    def test_warm_white_mireds(self) -> None:
        """Test handling of warm white color temp (high mireds)."""
        params = FadeParams(from_color_temp_mireds=500)  # ~2000K
        state = {}

        result = _resolve_start_mireds(params, state)

        assert result == 500

    def test_cool_white_mireds(self) -> None:
        """Test handling of cool white color temp (low mireds)."""
        params = FadeParams(from_color_temp_mireds=154)  # ~6500K
        state = {}

        result = _resolve_start_mireds(params, state)

        assert result == 154

    def test_state_with_integer_mireds(self) -> None:
        """Test handling of integer mireds from state."""
        params = FadeParams()
        state = {"color_temp": 286}  # ~3500K

        result = _resolve_start_mireds(params, state)

        assert result == 286
