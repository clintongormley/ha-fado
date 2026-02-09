"""Tests for ExpectedState color matching functionality."""

from __future__ import annotations

from custom_components.fado.expected_state import ExpectedState, ExpectedValues


class TestExpectedStateColorMatching:
    """Test ExpectedState with ExpectedValues for color matching."""

    def test_match_brightness_only(self) -> None:
        """Test matching when only brightness is tracked."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128))

        # Exact match
        result = state.match_and_remove(ExpectedValues(brightness=128))
        assert result is not None
        assert result.brightness == 128
        assert state.is_empty

    def test_match_brightness_with_tolerance(self) -> None:
        """Test brightness within +/-3 tolerance matches."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128))

        # Within tolerance (+3)
        result = state.match_and_remove(ExpectedValues(brightness=131))
        assert result is not None
        assert result.brightness == 128
        assert state.is_empty

    def test_no_match_brightness_outside_tolerance(self) -> None:
        """Test brightness outside tolerance doesn't match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128))

        # Outside tolerance (+4)
        result = state.match_and_remove(ExpectedValues(brightness=132))
        assert result is None
        assert not state.is_empty

    def test_match_hs_color_only(self) -> None:
        """Test matching when only HS color is tracked."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(hs_color=(180.0, 50.0)))

        # Exact match
        result = state.match_and_remove(ExpectedValues(hs_color=(180.0, 50.0)))
        assert result is not None
        assert result.hs_color == (180.0, 50.0)
        assert state.is_empty

    def test_match_hs_with_tolerance(self) -> None:
        """Test HS within tolerance (hue +/-5, sat +/-3) matches."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(hs_color=(180.0, 50.0)))

        # Within tolerance (hue +5, sat +3)
        result = state.match_and_remove(ExpectedValues(hs_color=(185.0, 53.0)))
        assert result is not None
        assert result.hs_color == (180.0, 50.0)
        assert state.is_empty

    def test_no_match_hue_outside_tolerance(self) -> None:
        """Test hue outside +/-5 tolerance doesn't match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(hs_color=(180.0, 50.0)))

        # Outside tolerance (hue +6)
        result = state.match_and_remove(ExpectedValues(hs_color=(186.0, 50.0)))
        assert result is None
        assert not state.is_empty

    def test_no_match_saturation_outside_tolerance(self) -> None:
        """Test saturation outside +/-3 tolerance doesn't match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(hs_color=(180.0, 50.0)))

        # Outside tolerance (sat +4)
        result = state.match_and_remove(ExpectedValues(hs_color=(180.0, 54.0)))
        assert result is None
        assert not state.is_empty

    def test_hue_wraparound_matching(self) -> None:
        """Test hue 358 matches hue 2 (both within 5 degrees of 0)."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(hs_color=(358.0, 50.0)))

        # Wraparound: 358 and 2 are 4 degrees apart (within 5 degree tolerance)
        result = state.match_and_remove(ExpectedValues(hs_color=(2.0, 50.0)))
        assert result is not None
        assert result.hs_color == (358.0, 50.0)
        assert state.is_empty

    def test_match_kelvin_only(self) -> None:
        """Test matching when only kelvin is tracked."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(color_temp_kelvin=3333))

        # Exact match
        result = state.match_and_remove(ExpectedValues(color_temp_kelvin=3333))
        assert result is not None
        assert result.color_temp_kelvin == 3333
        assert state.is_empty

    def test_match_kelvin_with_tolerance(self) -> None:
        """Test kelvin within +/-100 tolerance matches."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(color_temp_kelvin=3333))

        # Within tolerance (+100)
        result = state.match_and_remove(ExpectedValues(color_temp_kelvin=3433))
        assert result is not None
        assert result.color_temp_kelvin == 3333
        assert state.is_empty

    def test_no_match_kelvin_outside_tolerance(self) -> None:
        """Test kelvin outside tolerance doesn't match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(color_temp_kelvin=3333))

        # Outside tolerance (+101)
        result = state.match_and_remove(ExpectedValues(color_temp_kelvin=3434))
        assert result is None
        assert not state.is_empty

    def test_match_brightness_and_hs(self) -> None:
        """Test both brightness and HS must match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128, hs_color=(180.0, 50.0)))

        # Both match
        result = state.match_and_remove(ExpectedValues(brightness=128, hs_color=(180.0, 50.0)))
        assert result is not None
        assert result.brightness == 128
        assert result.hs_color == (180.0, 50.0)
        assert state.is_empty

    def test_no_match_when_brightness_wrong(self) -> None:
        """Test color matches but brightness doesn't = no match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128, hs_color=(180.0, 50.0)))

        # Color matches, brightness doesn't
        result = state.match_and_remove(ExpectedValues(brightness=200, hs_color=(180.0, 50.0)))
        assert result is None
        assert not state.is_empty

    def test_no_match_when_color_wrong(self) -> None:
        """Test brightness matches but color doesn't = no match."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128, hs_color=(180.0, 50.0)))

        # Brightness matches, color doesn't
        result = state.match_and_remove(ExpectedValues(brightness=128, hs_color=(90.0, 50.0)))
        assert result is None
        assert not state.is_empty

    def test_ignores_untracked_dimensions(self) -> None:
        """Test if only tracking brightness, color in actual doesn't matter."""
        state = ExpectedState(entity_id="light.test")
        state.add(ExpectedValues(brightness=128))  # Only tracking brightness

        # Actual has color, but we only check brightness
        result = state.match_and_remove(ExpectedValues(brightness=128, hs_color=(180.0, 50.0)))
        assert result is not None
        assert result.brightness == 128
        assert state.is_empty

    def test_brightness_range_match_intermediate_value(self) -> None:
        """Test range matching accepts intermediate brightness values."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from 10 -> 100
        expected = ExpectedValues(brightness=100, from_brightness=10)
        expected_state.add(expected)

        # Intermediate value during transition, old state consistent with range
        actual = ExpectedValues(brightness=50)
        old = ExpectedValues(brightness=30)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        # Should NOT remove (range match, waiting for final value)
        assert len(expected_state.values) == 1

    def test_brightness_range_match_final_value(self) -> None:
        """Test range matching removes on final target value."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from 10 -> 100
        expected = ExpectedValues(brightness=100, from_brightness=10)
        expected_state.add(expected)

        # Final value (within tolerance of target), old state consistent
        actual = ExpectedValues(brightness=98)
        old = ExpectedValues(brightness=90)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        # Should remove (exact match)
        assert len(expected_state.values) == 0

    def test_brightness_range_match_outside_range(self) -> None:
        """Test range matching rejects values outside range."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from 10 -> 100
        expected = ExpectedValues(brightness=100, from_brightness=10)
        expected_state.add(expected)

        # Value outside range
        actual = ExpectedValues(brightness=150)

        matched = expected_state.match_and_remove(actual)
        assert matched is None
        assert len(expected_state.values) == 1

    def test_brightness_point_match_unchanged(self) -> None:
        """Test point matching behavior unchanged when no from_brightness."""
        expected_state = ExpectedState(entity_id="light.test")

        # Point-based (no from_brightness)
        expected = ExpectedValues(brightness=100)
        expected_state.add(expected)

        # Within tolerance
        actual = ExpectedValues(brightness=98)

        matched = expected_state.match_and_remove(actual)
        assert matched == expected
        # Should remove (exact match)
        assert len(expected_state.values) == 0

    def test_hs_range_match_no_wraparound(self) -> None:
        """Test HS range matching without hue wraparound."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from (100, 50) -> (150, 80)
        expected = ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0))
        expected_state.add(expected)

        # Intermediate value, old state consistent with range
        actual = ExpectedValues(hs_color=(125.0, 65.0))
        old = ExpectedValues(hs_color=(110.0, 55.0))

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        assert len(expected_state.values) == 1  # Range match, not removed

    def test_hs_range_match_with_wraparound(self) -> None:
        """Test HS range matching with hue wraparound (350->10)."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from (350, 50) -> (10, 50)
        expected = ExpectedValues(hs_color=(10.0, 50.0), from_hs_color=(350.0, 50.0))
        expected_state.add(expected)

        # Intermediate values in wraparound range (not near target)
        old = ExpectedValues(hs_color=(350.0, 50.0))
        for test_hue in [355.0, 0.0]:
            actual = ExpectedValues(hs_color=(test_hue, 50.0))
            matched = expected_state.match_and_remove(actual, old=old)
            assert matched == expected
            assert len(expected_state.values) == 1  # Range match, not removed

        # Value close to target (within tolerance) - should be exact match
        actual = ExpectedValues(hs_color=(8.0, 50.0))
        old = ExpectedValues(hs_color=(0.0, 50.0))
        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        assert len(expected_state.values) == 0  # Exact match, removed

    def test_hs_range_match_wraparound_rejects_gap(self) -> None:
        """Test HS range matching rejects values in the wraparound gap."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from (350, 50) -> (10, 50)
        expected = ExpectedValues(hs_color=(10.0, 50.0), from_hs_color=(350.0, 50.0))
        expected_state.add(expected)

        # Value in the gap (should be rejected)
        actual = ExpectedValues(hs_color=(180.0, 50.0))

        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_hs_exact_match_removes(self) -> None:
        """Test HS exact match removes from queue."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition with range
        expected = ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0))
        expected_state.add(expected)

        # Target value (within tolerance), old state consistent
        actual = ExpectedValues(hs_color=(148.0, 79.0))
        old = ExpectedValues(hs_color=(140.0, 75.0))

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        assert len(expected_state.values) == 0  # Exact match, removed

    def test_kelvin_range_match_intermediate_value(self) -> None:
        """Test kelvin range matching accepts intermediate values."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from 2700K -> 6500K
        expected = ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700)
        expected_state.add(expected)

        # Intermediate value, old state consistent with range
        actual = ExpectedValues(color_temp_kelvin=4000)
        old = ExpectedValues(color_temp_kelvin=3500)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        assert len(expected_state.values) == 1  # Range match

    def test_kelvin_range_match_final_value(self) -> None:
        """Test kelvin range matching removes on target value."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from 2700K -> 6500K
        expected = ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700)
        expected_state.add(expected)

        # Target value (within tolerance), old state consistent
        actual = ExpectedValues(color_temp_kelvin=6450)
        old = ExpectedValues(color_temp_kelvin=6000)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched == expected
        assert len(expected_state.values) == 0  # Exact match, removed

    def test_kelvin_range_match_outside_range(self) -> None:
        """Test kelvin range matching rejects out of range values."""
        expected_state = ExpectedState(entity_id="light.test")

        # Transition from 2700K -> 6500K
        expected = ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700)
        expected_state.add(expected)

        # Out of range
        actual = ExpectedValues(color_temp_kelvin=7000)

        matched = expected_state.match_and_remove(actual)
        assert matched is None


class TestExpectedValuesFormatting:
    """Test ExpectedValues __str__ and format_transition."""

    def test_str_brightness_only(self) -> None:
        assert str(ExpectedValues(brightness=100)) == "(brightness=100)"

    def test_str_brightness_with_from(self) -> None:
        assert str(ExpectedValues(brightness=100, from_brightness=10)) == "(brightness=10->100)"

    def test_str_hs_color_only(self) -> None:
        assert str(ExpectedValues(hs_color=(180.0, 50.0))) == "(hs_color=(180.0, 50.0))"

    def test_str_hs_color_with_from(self) -> None:
        ev = ExpectedValues(hs_color=(180.0, 50.0), from_hs_color=(100.0, 30.0))
        assert str(ev) == "(hs_color=(100.0, 30.0)->(180.0, 50.0))"

    def test_str_kelvin_only(self) -> None:
        assert str(ExpectedValues(color_temp_kelvin=4000)) == "(color_temp_kelvin=4000)"

    def test_str_kelvin_with_from(self) -> None:
        ev = ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700)
        assert str(ev) == "(color_temp_kelvin=2700->6500)"

    def test_str_empty(self) -> None:
        assert str(ExpectedValues()) == "(empty)"

    def test_str_multi_dimension(self) -> None:
        ev = ExpectedValues(brightness=200, hs_color=(120.0, 80.0))
        assert str(ev) == "(brightness=200, hs_color=(120.0, 80.0))"

    def test_format_transition_with_old(self) -> None:
        old = ExpectedValues(brightness=28, hs_color=(240.0, 100.0))
        actual = ExpectedValues(brightness=41, hs_color=(240.0, 100.0))
        result = ExpectedValues.format_transition(old, actual)
        assert result == "(brightness=28->41, hs_color=(240.0, 100.0)->(240.0, 100.0))"

    def test_format_transition_without_old(self) -> None:
        actual = ExpectedValues(brightness=41)
        result = ExpectedValues.format_transition(None, actual)
        assert result == "(brightness=41)"

    def test_format_transition_old_missing_dimension(self) -> None:
        old = ExpectedValues(brightness=28)
        actual = ExpectedValues(brightness=41, hs_color=(180.0, 50.0))
        result = ExpectedValues.format_transition(old, actual)
        assert result == "(brightness=28->41, hs_color=(180.0, 50.0))"

    def test_format_transition_kelvin(self) -> None:
        old = ExpectedValues(color_temp_kelvin=3000)
        actual = ExpectedValues(color_temp_kelvin=4500)
        result = ExpectedValues.format_transition(old, actual)
        assert result == "(color_temp_kelvin=3000->4500)"

    def test_format_transition_empty(self) -> None:
        result = ExpectedValues.format_transition(None, ExpectedValues())
        assert result == "(empty)"


class TestOldStateValidation:
    """Test that range matches require old state to be consistent with the transition."""

    # --- Brightness ---

    def test_brightness_range_rejects_when_old_is_none(self) -> None:
        """Range match rejected when no old state provided."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        actual = ExpectedValues(brightness=50)
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_brightness_range_rejects_off_to_on(self) -> None:
        """Range match rejected when old state was off (brightness=0).

        This is the core bug fix: stale range [10,100] should not match
        when user turns light from off to on (brightness=0 -> 92).
        """
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        actual = ExpectedValues(brightness=92)
        old = ExpectedValues(brightness=0)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None

    def test_brightness_range_rejects_unrelated_change(self) -> None:
        """Range match rejected when old brightness is outside the range.

        User manually changed brightness from 200 to 50 — not part of
        the expected 10->100 transition.
        """
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        actual = ExpectedValues(brightness=50)
        old = ExpectedValues(brightness=200)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None

    def test_brightness_range_accepts_old_at_range_boundary(self) -> None:
        """Range match accepted when old brightness is at range boundary (within tolerance)."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        actual = ExpectedValues(brightness=50)
        old = ExpectedValues(brightness=10)  # Exactly at from_brightness

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None

    def test_brightness_range_accepts_old_within_tolerance(self) -> None:
        """Range match accepted when old brightness is just outside range but within tolerance."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        actual = ExpectedValues(brightness=50)
        old = ExpectedValues(brightness=7)  # 10 - 3 = 7, at tolerance boundary

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None

    def test_brightness_exact_match_rejects_without_old(self) -> None:
        """Native transition exact match also rejected without old state."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        # Actual matches target exactly (within tolerance)
        actual = ExpectedValues(brightness=99)

        # No old state — native transition match rejected
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_brightness_exact_match_accepts_with_consistent_old(self) -> None:
        """Native transition exact match accepted when old is consistent."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=10))

        actual = ExpectedValues(brightness=99)
        old = ExpectedValues(brightness=90)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None
        assert len(expected_state.values) == 0  # Exact match removes

    def test_brightness_point_exact_match_ignores_old(self) -> None:
        """Point match (no from_*) works without old state."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100))

        actual = ExpectedValues(brightness=99)
        matched = expected_state.match_and_remove(actual)
        assert matched is not None
        assert len(expected_state.values) == 0

    # --- HS Color ---

    def test_hs_range_rejects_when_old_is_none(self) -> None:
        """HS range match rejected when no old state provided."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0)))

        actual = ExpectedValues(hs_color=(125.0, 65.0))
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_hs_range_rejects_unrelated_color(self) -> None:
        """HS range match rejected when old color is outside the range."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0)))

        actual = ExpectedValues(hs_color=(125.0, 65.0))
        old = ExpectedValues(hs_color=(300.0, 90.0))  # Completely unrelated

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None

    def test_hs_exact_match_rejects_without_old(self) -> None:
        """HS native transition exact match also rejected without old state."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0)))

        actual = ExpectedValues(hs_color=(150.0, 80.0))
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_hs_exact_match_accepts_with_consistent_old(self) -> None:
        """HS native transition exact match accepted when old is consistent."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0)))

        actual = ExpectedValues(hs_color=(150.0, 80.0))
        old = ExpectedValues(hs_color=(140.0, 75.0))

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None
        assert len(expected_state.values) == 0

    def test_hs_point_exact_match_ignores_old(self) -> None:
        """HS point match (no from_*) works without old state."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(150.0, 80.0)))

        actual = ExpectedValues(hs_color=(150.0, 80.0))
        matched = expected_state.match_and_remove(actual)
        assert matched is not None
        assert len(expected_state.values) == 0

    # --- Kelvin ---

    def test_kelvin_range_rejects_when_old_is_none(self) -> None:
        """Kelvin range match rejected when no old state provided."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700))

        actual = ExpectedValues(color_temp_kelvin=4000)
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_kelvin_range_rejects_unrelated_change(self) -> None:
        """Kelvin range match rejected when old kelvin is outside the range."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700))

        actual = ExpectedValues(color_temp_kelvin=4000)
        old = ExpectedValues(color_temp_kelvin=1800)  # Below range

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None

    def test_kelvin_range_accepts_consistent_old(self) -> None:
        """Kelvin range match accepted when old kelvin is within range."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700))

        actual = ExpectedValues(color_temp_kelvin=4000)
        old = ExpectedValues(color_temp_kelvin=3500)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None
        assert len(expected_state.values) == 1  # Range match, not removed

    def test_kelvin_exact_match_rejects_without_old(self) -> None:
        """Kelvin native transition exact match also rejected without old state."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700))

        actual = ExpectedValues(color_temp_kelvin=6500)
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_kelvin_exact_match_accepts_with_consistent_old(self) -> None:
        """Kelvin native transition exact match accepted when old is consistent."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700))

        actual = ExpectedValues(color_temp_kelvin=6500)
        old = ExpectedValues(color_temp_kelvin=6000)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None
        assert len(expected_state.values) == 0

    def test_kelvin_point_exact_match_ignores_old(self) -> None:
        """Kelvin point match (no from_*) works without old state."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500))

        actual = ExpectedValues(color_temp_kelvin=6500)
        matched = expected_state.match_and_remove(actual)
        assert matched is not None
        assert len(expected_state.values) == 0


class TestEdgeCases:
    """Test edge cases for match logic coverage."""

    def test_brightness_zero_exact_match_with_from(self) -> None:
        """Fade to off with native transition: brightness=0 target with from_brightness."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=0, from_brightness=50))

        actual = ExpectedValues(brightness=0)
        old = ExpectedValues(brightness=30)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is not None
        assert len(expected_state.values) == 0  # Exact match

    def test_brightness_zero_point_match(self) -> None:
        """Fade to off without from_*: brightness=0 point match."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=0))

        actual = ExpectedValues(brightness=0)
        matched = expected_state.match_and_remove(actual)
        assert matched is not None
        assert len(expected_state.values) == 0

    def test_brightness_zero_point_no_match(self) -> None:
        """Point match brightness=0 does not match non-zero actual."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=0))

        actual = ExpectedValues(brightness=50)
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_from_brightness_actual_outside_range_returns_none(self) -> None:
        """Native transition rejects actual outside range even with consistent old."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100, from_brightness=50))

        actual = ExpectedValues(brightness=200)  # Above range, not within tolerance
        old = ExpectedValues(brightness=60)

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None

    def test_actual_brightness_none_returns_none(self) -> None:
        """Actual brightness=None returns no match."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(brightness=100))

        actual = ExpectedValues()  # No brightness
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_actual_hs_none_returns_none(self) -> None:
        """Actual hs_color=None returns no match when expected tracks HS."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(180.0, 50.0)))

        actual = ExpectedValues()  # No hs_color
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_actual_kelvin_none_returns_none(self) -> None:
        """Actual color_temp_kelvin=None returns no match when expected tracks kelvin."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=4000))

        actual = ExpectedValues()  # No color_temp_kelvin
        matched = expected_state.match_and_remove(actual)
        assert matched is None

    def test_hs_native_transition_actual_outside_range(self) -> None:
        """HS native transition rejects actual outside range even with consistent old."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(hs_color=(150.0, 80.0), from_hs_color=(100.0, 50.0)))

        # Actual is way outside the from->to range (hue=250, sat=20)
        actual = ExpectedValues(hs_color=(250.0, 20.0))
        old = ExpectedValues(hs_color=(120.0, 60.0))  # Old is within range

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None

    def test_kelvin_native_transition_actual_outside_range(self) -> None:
        """Kelvin native transition rejects actual outside range even with consistent old."""
        expected_state = ExpectedState(entity_id="light.test")
        expected_state.add(ExpectedValues(color_temp_kelvin=6500, from_color_temp_kelvin=2700))

        # Actual is outside range (8000K) and not within tolerance of target
        actual = ExpectedValues(color_temp_kelvin=8000)
        old = ExpectedValues(color_temp_kelvin=3000)  # Old is within range

        matched = expected_state.match_and_remove(actual, old=old)
        assert matched is None
