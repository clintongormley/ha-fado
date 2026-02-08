"""Tests for the FadeChange.resolve() method."""

from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_SUPPORTED_COLOR_MODES
from homeassistant.components.light import ATTR_COLOR_TEMP_KELVIN as HA_ATTR_COLOR_TEMP_KELVIN
from homeassistant.components.light import ATTR_HS_COLOR as HA_ATTR_HS_COLOR
from homeassistant.components.light.const import ColorMode

from custom_components.fado.fade_change import FadeChange
from custom_components.fado.fade_params import FadeParams


class TestResolveFadeBasicStructure:
    """Test basic return type and structure of FadeChange.resolve."""

    def test_returns_fade_change_or_none(self) -> None:
        """Test that the function returns a FadeChange object or None."""
        params = FadeParams(brightness_pct=50, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 100,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert isinstance(change, FadeChange)

    def test_returns_none_when_nothing_to_fade(self) -> None:
        """Test that None is returned when there's nothing to change."""
        params = FadeParams(transition_ms=1000)  # No target values
        state = {
            ATTR_BRIGHTNESS: 100,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is None

    def test_returns_none_when_target_equals_current(self) -> None:
        """Test that None is returned when target equals current state."""
        params = FadeParams(brightness_pct=50, transition_ms=1000)  # 50% = int(127.5) = 127
        state = {
            ATTR_BRIGHTNESS: 127,  # Current brightness matches target
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is None


class TestResolveFadeSimpleBrightnessFade:
    """Test simple brightness-only fade scenarios."""

    def test_brightness_fade_values(self) -> None:
        """Test that brightness values are correctly resolved."""
        params = FadeParams(brightness_pct=75, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 100,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_brightness == 100
        # 75% of 255 = 191
        assert change.end_brightness == 191

    def test_brightness_fade_from_override(self) -> None:
        """Test that from_brightness_pct overrides state brightness."""
        params = FadeParams(
            brightness_pct=100,
            from_brightness_pct=25,
            transition_ms=1000,
        )
        state = {
            ATTR_BRIGHTNESS: 200,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # 25% of 255 = int(63.75) = 63
        assert change.start_brightness == 63
        assert change.end_brightness == 255

    def test_brightness_fade_no_color_attributes(self) -> None:
        """Test that brightness-only fade has no color attributes."""
        params = FadeParams(brightness_pct=50, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 100,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_hs is None
        assert change.end_hs is None
        assert change.start_mireds is None
        assert change.end_mireds is None


class TestResolveFadeSimpleHsFade:
    """Test simple HS color fade scenarios."""

    def test_hs_color_fade_values(self) -> None:
        """Test that HS color values are correctly resolved."""
        params = FadeParams(
            hs_color=(120.0, 80.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (60.0, 50.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_hs == (60.0, 50.0)
        assert change.end_hs == (120.0, 80.0)

    def test_hs_color_fade_from_override(self) -> None:
        """Test that from_hs_color overrides state HS color."""
        params = FadeParams(
            hs_color=(240.0, 100.0),
            from_hs_color=(0.0, 100.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (180.0, 50.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_hs == (0.0, 100.0)
        assert change.end_hs == (240.0, 100.0)

    def test_hs_color_only_no_mireds(self) -> None:
        """Test that HS-only fade has no mireds attributes."""
        params = FadeParams(
            hs_color=(120.0, 80.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (60.0, 50.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_mireds is None
        assert change.end_mireds is None


class TestResolveFadeSimpleColorTempFade:
    """Test simple color temperature fade scenarios."""

    def test_color_temp_fade_values(self) -> None:
        """Test that color temp values are correctly converted to mireds."""
        params = FadeParams(
            color_temp_kelvin=2500,  # 400 mireds
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 5000,  # 200 mireds
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_mireds == 200
        assert change.end_mireds == 400

    def test_color_temp_fade_from_override(self) -> None:
        """Test that from_color_temp_kelvin overrides state kelvin."""
        params = FadeParams(
            color_temp_kelvin=2000,  # 500 mireds
            from_color_temp_kelvin=6500,  # 153 mireds (int(1_000_000/6500))
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 3000,  # ~333 mireds
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_mireds == 153
        assert change.end_mireds == 500

    def test_color_temp_only_no_hs(self) -> None:
        """Test that color temp only fade has no HS attributes."""
        params = FadeParams(
            color_temp_kelvin=3000,  # ~333 mireds
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 4000,  # ~250 mireds
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.start_hs is None
        assert change.end_hs is None


class TestResolveFadeHybridTransitions:
    """Test hybrid HS <-> color temp transition detection."""

    def test_off_locus_hs_to_color_temp_is_hybrid(self) -> None:
        """Test that off-locus HS to color temp creates hybrid FadeChange."""
        params = FadeParams(
            color_temp_kelvin=3000,  # ~333 mireds
            transition_ms=1000,
        )
        # High saturation HS (off Planckian locus)
        state = {
            HA_ATTR_HS_COLOR: (120.0, 80.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # Should be hybrid - has hybrid_direction set
        assert change.hybrid_direction == "hs_to_mireds"
        assert change.crossover_step is not None
        assert change._crossover_hs is not None
        assert change._crossover_mireds is not None

    def test_color_temp_to_hs_is_hybrid(self) -> None:
        """Test that color temp to HS creates hybrid FadeChange."""
        params = FadeParams(
            hs_color=(120.0, 80.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 3000,  # ~333 mireds
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # Should be hybrid - has hybrid_direction set
        assert change.hybrid_direction == "mireds_to_hs"
        assert change.crossover_step is not None
        assert change._crossover_hs is not None
        assert change._crossover_mireds is not None

    def test_on_locus_hs_to_color_temp_is_not_hybrid(self) -> None:
        """Test that on-locus HS to color temp is simple (not hybrid)."""
        params = FadeParams(
            color_temp_kelvin=3000,  # ~333 mireds
            transition_ms=1000,
        )
        # Low saturation HS (on Planckian locus)
        state = {
            HA_ATTR_HS_COLOR: (35.0, 10.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # Should NOT be hybrid
        assert change.hybrid_direction is None

    def test_hs_to_hs_is_not_hybrid(self) -> None:
        """Test that HS to HS is simple (not hybrid)."""
        params = FadeParams(
            hs_color=(240.0, 100.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (120.0, 80.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.hybrid_direction is None

    def test_both_targets_specified_is_not_hybrid(self) -> None:
        """Test that specifying both HS and color temp targets is not hybrid."""
        params = FadeParams(
            hs_color=(240.0, 100.0),  # Specifying HS target
            color_temp_kelvin=3000,  # And also color temp target
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (120.0, 80.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.hybrid_direction is None


class TestResolveFadeHybridStepGeneration:
    """Test that hybrid FadeChange generates correct steps across crossover."""

    def test_hs_to_mireds_generates_hs_before_crossover(self) -> None:
        """Test that HS->mireds hybrid emits hs_color before crossover."""
        params = FadeParams(
            color_temp_kelvin=3000,
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (120.0, 80.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.hybrid_direction == "hs_to_mireds"

        # Get first step (should be HS)
        step = change.next_step()
        assert step.hs_color is not None
        assert step.color_temp_kelvin is None

    def test_hs_to_mireds_generates_color_temp_after_crossover(self) -> None:
        """Test that HS->mireds hybrid emits color_temp_kelvin after crossover."""
        params = FadeParams(
            color_temp_kelvin=3000,
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (120.0, 80.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None

        # Iterate through all steps
        steps_with_hs = 0
        steps_with_kelvin = 0
        while change.has_next():
            step = change.next_step()
            if step.hs_color is not None:
                steps_with_hs += 1
            if step.color_temp_kelvin is not None:
                steps_with_kelvin += 1

        # Should have both HS and color_temp steps
        assert steps_with_hs > 0
        assert steps_with_kelvin > 0

    def test_mireds_to_hs_generates_color_temp_before_crossover(self) -> None:
        """Test that mireds->HS hybrid emits color_temp_kelvin before crossover."""
        params = FadeParams(
            hs_color=(120.0, 80.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 3000,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.hybrid_direction == "mireds_to_hs"

        # Get first step (should be color_temp)
        step = change.next_step()
        assert step.color_temp_kelvin is not None
        assert step.hs_color is None

    def test_mireds_to_hs_generates_hs_after_crossover(self) -> None:
        """Test that mireds->HS hybrid emits hs_color after crossover."""
        params = FadeParams(
            hs_color=(120.0, 80.0),
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 3000,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None

        # Iterate through all steps
        steps_with_hs = 0
        steps_with_kelvin = 0
        while change.has_next():
            step = change.next_step()
            if step.hs_color is not None:
                steps_with_hs += 1
            if step.color_temp_kelvin is not None:
                steps_with_kelvin += 1

        # Should have both color_temp and HS steps
        assert steps_with_kelvin > 0
        assert steps_with_hs > 0


class TestResolveFadeNonDimmableLights:
    """Test handling of non-dimmable (on/off only) lights."""

    def test_non_dimmable_light_returns_single_step(self) -> None:
        """Test that non-dimmable light gets single step FadeChange."""
        params = FadeParams(brightness_pct=100, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 0,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF],  # On/off only
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.end_brightness == 255
        assert change.transition_ms == 0  # Zero transition for on/off
        assert change.step_count() == 1

    def test_non_dimmable_light_turns_off(self) -> None:
        """Test that non-dimmable light can be turned off."""
        params = FadeParams(brightness_pct=0, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 255,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.end_brightness == 0

    def test_non_dimmable_light_ignores_color_params(self) -> None:
        """Test that non-dimmable light ignores color parameters."""
        params = FadeParams(
            brightness_pct=100,
            hs_color=(120.0, 80.0),  # This should be ignored
            transition_ms=1000,
        )
        state = {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.end_hs is None
        assert change.end_mireds is None


class TestResolveFadeCapabilityFiltering:
    """Test capability-based filtering of color modes."""

    def test_color_temp_converted_to_hs_when_not_supported(self) -> None:
        """Test that color temp is converted to HS when light only supports HS."""
        params = FadeParams(
            color_temp_kelvin=3000,  # Target color temp
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (120.0, 50.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],  # Only HS, no COLOR_TEMP
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # Should have converted to HS
        assert change.end_hs is not None
        assert change.end_mireds is None

    def test_hs_dropped_when_only_color_temp_supported(self) -> None:
        """Test that HS is dropped when light only supports color temp."""
        params = FadeParams(
            hs_color=(120.0, 80.0),  # High saturation - can't convert
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 3000,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],  # Only color temp, no HS
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        # Should return None since HS can't be applied
        assert change is None

    def test_hs_converted_to_mireds_when_on_locus(self) -> None:
        """Test that low-saturation HS is converted to mireds when appropriate."""
        params = FadeParams(
            hs_color=(35.0, 10.0),  # On locus - can convert
            transition_ms=1000,
        )
        state = {
            HA_ATTR_COLOR_TEMP_KELVIN: 5000,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP],  # Only color temp
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # Should have converted to mireds
        assert change.end_mireds is not None
        assert change.end_hs is None


class TestResolveFadeTimingParameters:
    """Test that timing parameters are correctly passed through."""

    def test_transition_ms_passed_to_change(self) -> None:
        """Test that transition_ms is passed to FadeChange."""
        params = FadeParams(brightness_pct=50, transition_ms=2000)
        state = {
            ATTR_BRIGHTNESS: 100,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.transition_ms == 2000

    def test_min_step_delay_ms_passed_to_change(self) -> None:
        """Test that min_step_delay_ms is passed to FadeChange."""
        params = FadeParams(brightness_pct=50, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 100,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=75)

        assert change is not None
        assert change.min_step_delay_ms == 75


class TestResolveFadeEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_state(self) -> None:
        """Test with empty state dictionary (light off)."""
        params = FadeParams(brightness_pct=50, transition_ms=1000)
        state = {
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # When light is off (no brightness), start_brightness is clamped to min (default=1)
        assert change.start_brightness == 1
        assert change.end_brightness == 127

    def test_saturation_threshold_boundary_on_locus(self) -> None:
        """Test saturation at exactly the threshold is considered on locus."""
        params = FadeParams(
            color_temp_kelvin=3000,
            transition_ms=1000,
        )
        # Saturation at threshold (15) - should be on locus
        state = {
            HA_ATTR_HS_COLOR: (35.0, 15.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # On locus means NOT hybrid
        assert change.hybrid_direction is None

    def test_saturation_threshold_boundary_off_locus(self) -> None:
        """Test saturation just above threshold is considered off locus."""
        params = FadeParams(
            color_temp_kelvin=3000,
            transition_ms=1000,
        )
        # Saturation just above threshold (16) - should be off locus
        state = {
            HA_ATTR_HS_COLOR: (35.0, 16.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        # Off locus means hybrid
        assert change.hybrid_direction == "hs_to_mireds"


class TestResolveFadeFromMatchesTarget:
    """Test resolve() when from==to but state differs.

    When from values differ from actual state, resolve() returns a FadeChange
    with from_step set (to apply the starting state) but has_fade=False
    (nothing to interpolate since from==to).
    """

    def test_from_hs_matches_target_returns_from_step(self) -> None:
        """from: {hs: green}, to: {hs: green}, state: color_temp → from_step only."""
        params = FadeParams(
            hs_color=(120.0, 100.0),
            from_hs_color=(120.0, 100.0),
            transition_ms=3000,
        )
        state = {
            ATTR_BRIGHTNESS: 255,
            HA_ATTR_COLOR_TEMP_KELVIN: 2739,
            "color_mode": ColorMode.COLOR_TEMP,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
            "min_color_temp_kelvin": 2000,
            "max_color_temp_kelvin": 6500,
        }

        fade = FadeChange.resolve(params, state, min_step_delay_ms=100)
        # from_step applies HS color since light is in COLOR_TEMP mode (different space)
        assert fade is not None
        assert fade.from_step is not None
        assert fade.from_step.hs_color == (120.0, 100.0)
        assert not fade.has_fade

    def test_from_color_temp_matches_target_returns_from_step(self) -> None:
        """from: {color_temp: 3000}, to: {color_temp: 3000}, state: HS → from_step only."""
        params = FadeParams(
            color_temp_kelvin=3000,
            from_color_temp_kelvin=3000,
            transition_ms=3000,
        )
        state = {
            ATTR_BRIGHTNESS: 255,
            HA_ATTR_HS_COLOR: (120.0, 100.0),
            "color_mode": ColorMode.HS,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
            "min_color_temp_kelvin": 2000,
            "max_color_temp_kelvin": 6500,
        }

        fade = FadeChange.resolve(params, state, min_step_delay_ms=100)
        # from_step applies color_temp since light is in HS mode (different space)
        assert fade is not None
        assert fade.from_step is not None
        assert fade.from_step.color_temp_kelvin == 3000
        assert not fade.has_fade

    def test_from_brightness_matches_target_returns_from_step(self) -> None:
        """from: {brightness_pct: 50}, to: {brightness_pct: 50}, state: 255 → from_step only."""
        params = FadeParams(
            brightness_pct=50,
            from_brightness_pct=50,
            transition_ms=1000,
        )
        state = {
            ATTR_BRIGHTNESS: 255,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        fade = FadeChange.resolve(params, state, min_step_delay_ms=100)
        # from_step applies brightness since 127 != 255 (actual state)
        assert fade is not None
        assert fade.from_step is not None
        assert fade.from_step.brightness == 127
        assert not fade.has_fade

    def test_from_matches_target_and_state_returns_none(self) -> None:
        """from==to==state → nothing to do at all, returns None."""
        params = FadeParams(
            brightness_pct=100,
            from_brightness_pct=100,
            transition_ms=1000,
        )
        state = {
            ATTR_BRIGHTNESS: 255,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        # from (255) matches actual state (255), so no from_step needed
        # from==to so no fade needed → None
        assert FadeChange.resolve(params, state, min_step_delay_ms=100) is None

    def test_no_from_values_same_target_returns_none(self) -> None:
        """Without explicit from, same target as state returns None."""
        params = FadeParams(
            brightness_pct=100,
            transition_ms=1000,
        )
        state = {
            ATTR_BRIGHTNESS: 255,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        assert FadeChange.resolve(params, state, min_step_delay_ms=100) is None


class TestBuildFromStep:
    """Test the _build_from_step utility function in fade_change.py."""

    def test_from_brightness_pct_differs_from_state(self) -> None:
        """Test building from step when brightness differs from state."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(brightness_pct=50, from_brightness_pct=50)
        state = {ATTR_BRIGHTNESS: 255}  # Actual differs from from (127)
        step = _build_from_step(params, state, min_brightness=1)
        assert step is not None
        assert step.brightness == 127
        assert step.hs_color is None
        assert step.color_temp_kelvin is None

    def test_from_brightness_pct_matches_state_returns_none(self) -> None:
        """Test that from step is None when brightness matches state."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(brightness_pct=50, from_brightness_pct=50)
        state = {ATTR_BRIGHTNESS: 127}  # Actual matches from (127)
        step = _build_from_step(params, state, min_brightness=1)
        assert step is None

    def test_from_brightness_raw(self) -> None:
        """Test building from step with raw brightness."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(brightness_pct=50, from_brightness=200)
        state = {ATTR_BRIGHTNESS: 100}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is not None
        assert step.brightness == 200

    def test_from_brightness_clamped_to_min(self) -> None:
        """Test that from brightness is clamped to min_brightness."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(brightness_pct=50, from_brightness=3)
        state = {ATTR_BRIGHTNESS: 100}
        step = _build_from_step(params, state, min_brightness=10)
        assert step is not None
        assert step.brightness == 10

    def test_from_hs_color_different_color_space(self) -> None:
        """Test from HS color when light is in COLOR_TEMP mode (always applies)."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(hs_color=(120.0, 100.0), from_hs_color=(120.0, 100.0))
        state = {"color_mode": ColorMode.COLOR_TEMP}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is not None
        assert step.hs_color == (120.0, 100.0)
        assert step.brightness is None

    def test_from_hs_color_same_color_space_differs(self) -> None:
        """Test from HS color when light is in HS mode with different color."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(hs_color=(120.0, 100.0), from_hs_color=(120.0, 100.0))
        state = {"color_mode": ColorMode.HS, HA_ATTR_HS_COLOR: (0.0, 50.0)}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is not None
        assert step.hs_color == (120.0, 100.0)

    def test_from_hs_color_same_color_space_matches(self) -> None:
        """Test from HS color when light already has same HS → None."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(hs_color=(120.0, 100.0), from_hs_color=(120.0, 100.0))
        state = {"color_mode": ColorMode.HS, HA_ATTR_HS_COLOR: (120.0, 100.0)}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is None

    def test_from_color_temp_different_color_space(self) -> None:
        """Test from color_temp when light is in HS mode (always applies)."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(color_temp_kelvin=3000, from_color_temp_kelvin=3000)
        state = {"color_mode": ColorMode.HS}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is not None
        assert step.color_temp_kelvin == 3000

    def test_from_color_temp_same_color_space_matches(self) -> None:
        """Test from color_temp when light already at same temp → None."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(color_temp_kelvin=3000, from_color_temp_kelvin=3000)
        state = {"color_mode": ColorMode.COLOR_TEMP, HA_ATTR_COLOR_TEMP_KELVIN: 3000}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is None

    def test_no_from_values_returns_none(self) -> None:
        """Test that no from values returns None."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(brightness_pct=50)
        state = {ATTR_BRIGHTNESS: 100}
        step = _build_from_step(params, state, min_brightness=1)
        assert step is None

    def test_from_brightness_pct_one_uses_min_brightness(self) -> None:
        """Test that brightness_pct=1 uses min_brightness when higher."""
        from custom_components.fado.fade_change import _build_from_step

        params = FadeParams(brightness_pct=50, from_brightness_pct=1)
        state = {ATTR_BRIGHTNESS: 100}
        # 1% of 255 = 2, but min_brightness is 10
        step = _build_from_step(params, state, min_brightness=10)
        assert step is not None
        assert step.brightness == 10


class TestResolveFadeFadeChangeIterator:
    """Test that returned FadeChange objects can generate steps."""

    def test_simple_change_generates_steps(self) -> None:
        """Test that simple FadeChange can generate steps."""
        params = FadeParams(brightness_pct=50, transition_ms=1000)
        state = {
            ATTR_BRIGHTNESS: 200,
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None
        assert change.step_count() >= 1

        total_steps = 0
        while change.has_next():
            step = change.next_step()
            assert step is not None
            total_steps += 1

        assert total_steps == change.step_count()

    def test_hybrid_change_generates_steps(self) -> None:
        """Test that hybrid FadeChange can generate steps."""
        params = FadeParams(
            color_temp_kelvin=3000,
            transition_ms=1000,
        )
        state = {
            HA_ATTR_HS_COLOR: (120.0, 80.0),
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS, ColorMode.COLOR_TEMP],
        }

        change = FadeChange.resolve(params, state, min_step_delay_ms=100)

        assert change is not None

        total_steps = 0
        while change.has_next():
            step = change.next_step()
            assert step is not None
            total_steps += 1

        assert total_steps > 0
        assert total_steps == change.step_count()
