"""Tests for the _calculate_step_count function."""

import pytest

from custom_components.fade_lights import _calculate_step_count


class TestCalculateStepCount:
    """Test cases for _calculate_step_count."""

    def test_time_constrained(self) -> None:
        """Test when time limits the number of steps.

        Brightness 0->255, 500ms, min_delay=100ms -> 5 steps (not 255)
        ideal=255, max_by_time=5 -> min(255,5)=5
        """
        result = _calculate_step_count(
            brightness_change=255,
            hue_change=None,
            sat_change=None,
            mireds_change=None,
            transition_ms=500,
            min_step_delay_ms=100,
        )
        assert result == 5

    def test_change_constrained(self) -> None:
        """Test when the change magnitude limits steps.

        Brightness 100->105, 10000ms, min_delay=100ms -> 5 steps (not 100)
        ideal=5, max_by_time=100 -> min(5,100)=5
        """
        result = _calculate_step_count(
            brightness_change=5,
            hue_change=None,
            sat_change=None,
            mireds_change=None,
            transition_ms=10000,
            min_step_delay_ms=100,
        )
        assert result == 5

    def test_balanced(self) -> None:
        """Test balanced case where both constraints matter.

        Brightness 50->200, 3000ms, min_delay=100ms -> 30 steps
        ideal=150, max_by_time=30 -> min(150,30)=30
        """
        result = _calculate_step_count(
            brightness_change=150,
            hue_change=None,
            sat_change=None,
            mireds_change=None,
            transition_ms=3000,
            min_step_delay_ms=100,
        )
        assert result == 30

    def test_brightness_dominates(self) -> None:
        """Test when brightness change dominates over saturation.

        Brightness 1->250 + saturation 50->51 -> ~249 ideal steps
        ideal=max(249,1)=249, max_by_time=300 -> 249
        """
        result = _calculate_step_count(
            brightness_change=249,
            hue_change=None,
            sat_change=1.0,
            mireds_change=None,
            transition_ms=30000,
            min_step_delay_ms=100,
        )
        assert result == 249

    def test_color_dominates(self) -> None:
        """Test when hue change dominates over brightness.

        Brightness 100->110 + hue 0->180 -> ~180 ideal steps
        ideal=max(10,180)=180, max_by_time=200 -> 180
        """
        result = _calculate_step_count(
            brightness_change=10,
            hue_change=180.0,
            sat_change=None,
            mireds_change=None,
            transition_ms=20000,
            min_step_delay_ms=100,
        )
        assert result == 180

    def test_single_dimension_brightness_only(self) -> None:
        """Test with only brightness changing.

        brightness_change=50, all others None, transition_ms=10000, min_step_delay_ms=100
        ideal=50, max_by_time=100 -> 50
        """
        result = _calculate_step_count(
            brightness_change=50,
            hue_change=None,
            sat_change=None,
            mireds_change=None,
            transition_ms=10000,
            min_step_delay_ms=100,
        )
        assert result == 50

    def test_mireds_only(self) -> None:
        """Test with only mireds changing.

        mireds_change=100 -> 20 steps (100/5=20)
        ideal=20, max_by_time=50 -> 20
        """
        result = _calculate_step_count(
            brightness_change=None,
            hue_change=None,
            sat_change=None,
            mireds_change=100,
            transition_ms=5000,
            min_step_delay_ms=100,
        )
        assert result == 20

    def test_no_changes_returns_one(self) -> None:
        """Test with all parameters None.

        All params None, transition_ms=1000, min_step_delay_ms=100
        ideal=1 (fallback), max_by_time=10 -> 1
        """
        result = _calculate_step_count(
            brightness_change=None,
            hue_change=None,
            sat_change=None,
            mireds_change=None,
            transition_ms=1000,
            min_step_delay_ms=100,
        )
        assert result == 1

    def test_minimum_bound_with_zero_change(self) -> None:
        """Test that zero changes still return at least 1.

        brightness_change=0, transition_ms=1000, min_step_delay_ms=100 -> 1
        """
        result = _calculate_step_count(
            brightness_change=0,
            hue_change=None,
            sat_change=None,
            mireds_change=None,
            transition_ms=1000,
            min_step_delay_ms=100,
        )
        assert result == 1

    def test_all_dimensions_changing(self) -> None:
        """Test with all dimensions changing simultaneously.

        The largest ideal step count should win.
        brightness=100, hue=50, sat=30, mireds=75
        ideal = max(100, 50, 30, 15) = 100
        max_by_time = 200
        result = min(100, 200) = 100
        """
        result = _calculate_step_count(
            brightness_change=100,
            hue_change=50.0,
            sat_change=30.0,
            mireds_change=75,  # 75 / 5 = 15
            transition_ms=20000,
            min_step_delay_ms=100,
        )
        assert result == 100

    def test_saturation_dominates(self) -> None:
        """Test when saturation change dominates.

        sat_change=80 -> ideal=80
        brightness_change=10 -> ideal=10
        max_by_time=150
        result = min(max(80,10), 150) = 80
        """
        result = _calculate_step_count(
            brightness_change=10,
            hue_change=None,
            sat_change=80.0,
            mireds_change=None,
            transition_ms=15000,
            min_step_delay_ms=100,
        )
        assert result == 80
