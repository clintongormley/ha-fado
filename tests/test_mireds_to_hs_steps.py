"""Tests for _build_mireds_to_hs_steps function."""

from custom_components.fade_lights import _build_mireds_to_hs_steps


class TestBuildMiredsToHsSteps:
    """Tests for the mireds-to-HS step builder."""

    def test_basic_transition_generates_steps(self):
        """Test that basic transition generates both mireds and HS steps."""
        # 3000K (333 mireds) to red (0, 100)
        steps = _build_mireds_to_hs_steps(
            start_mireds=333,
            end_hs=(0.0, 100.0),
            transition_ms=10000,
            min_step_delay_ms=100,
        )

        assert len(steps) > 0

        # First steps should have mireds, no HS
        assert steps[0].color_temp_mireds is not None
        assert steps[0].hs_color is None

        # Last steps should have HS, no mireds
        assert steps[-1].hs_color is not None
        assert steps[-1].color_temp_mireds is None

        # Final step should be the target
        assert steps[-1].hs_color == (0.0, 100.0)

    def test_phase_split_approximately_30_70(self):
        """Test that steps are split roughly 30% mireds, 70% HS."""
        steps = _build_mireds_to_hs_steps(
            start_mireds=333,
            end_hs=(0.0, 100.0),
            transition_ms=10000,
            min_step_delay_ms=100,
        )

        mireds_steps = [s for s in steps if s.color_temp_mireds is not None]
        hs_steps = [s for s in steps if s.hs_color is not None]

        total = len(steps)
        mireds_ratio = len(mireds_steps) / total
        hs_ratio = len(hs_steps) / total

        # Allow some tolerance: 20-40% mireds, 60-80% HS
        assert 0.2 <= mireds_ratio <= 0.4, f"Mireds ratio {mireds_ratio} out of range"
        assert 0.6 <= hs_ratio <= 0.8, f"HS ratio {hs_ratio} out of range"

    def test_mireds_steps_move_toward_target_hue(self):
        """Test that mireds steps move along locus toward target."""
        # Start at warm (333 mireds = 3000K), target blue-ish hue
        steps = _build_mireds_to_hs_steps(
            start_mireds=333,
            end_hs=(240.0, 80.0),  # Blue
            transition_ms=10000,
            min_step_delay_ms=100,
        )

        mireds_steps = [s for s in steps if s.color_temp_mireds is not None]
        assert len(mireds_steps) >= 2

        # Mireds should be changing (moving along locus)
        first_mireds = mireds_steps[0].color_temp_mireds
        last_mireds = mireds_steps[-1].color_temp_mireds
        assert first_mireds != last_mireds

    def test_hs_steps_end_at_target(self):
        """Test that HS steps interpolate toward target."""
        target_hs = (120.0, 75.0)  # Green
        steps = _build_mireds_to_hs_steps(
            start_mireds=250,
            end_hs=target_hs,
            transition_ms=5000,
            min_step_delay_ms=100,
        )

        hs_steps = [s for s in steps if s.hs_color is not None]
        assert len(hs_steps) >= 2

        # Last HS step should match target
        final_hs = hs_steps[-1].hs_color
        assert abs(final_hs[0] - target_hs[0]) < 0.1
        assert abs(final_hs[1] - target_hs[1]) < 0.1

    def test_no_brightness_in_steps(self):
        """Test that steps don't include brightness (handled separately)."""
        steps = _build_mireds_to_hs_steps(
            start_mireds=333,
            end_hs=(0.0, 100.0),
            transition_ms=5000,
            min_step_delay_ms=100,
        )

        for step in steps:
            assert step.brightness is None
