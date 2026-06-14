# Native-transition moving-anchor matching — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop native-transition fades from being falsely flagged as manual intervention, by anchoring each step's match window to the *last reported value* (a moving anchor) instead of the previous commanded target — while keeping (and tightening) genuine manual-intervention detection.

**Architecture:** For native-transition fades the coordinator enables a "moving anchor" mode on `ExpectedState`, seeding a per-dimension anchor at the fade's start value. Matching uses `[anchor … step-target]` as the window (instead of the entry's `from_*`), and the anchor advances to each matched report. Per-step entries, hybrid handling, flush/coalesce logic, and software stepping (`native_transitions=False`) are all unchanged. See spec: `docs/superpowers/specs/2026-06-14-native-transition-moving-anchor-design.md`.

**Tech Stack:** Python 3, Home Assistant custom integration, pytest (`-n auto`, `asyncio_mode=auto`), ruff, pyright.

---

## File Structure

- `custom_components/fado/fade_change.py` — add three hybrid-aware anchor accessors (`anchor_brightness`, `anchor_hs`, `anchor_color_temp_kelvin`) to `FadeChange`. These expose the value each dimension fades *from* (phase-aware for hybrid).
- `custom_components/fado/expected_state.py` — add moving-anchor state + `set_moving_anchor`/`clear_moving_anchor` to `ExpectedState`; use the anchor as the range "from" bound in `_brightness_match`/`_kelvin_match`/`_hs_match`; advance anchors on each matched report in `match_and_remove`; clear anchors in `wait_and_clear`.
- `custom_components/fado/coordinator.py` — add `_configure_moving_anchor(...)` and call it at the start of `_run_fade_loop`: enable + seed for native fades, clear for software fades.
- `tests/test_fade_change.py` — anchor-accessor unit tests.
- `tests/test_expected_state_colors.py` — moving-anchor matching unit tests (the main TDD coverage).
- `tests/test_manual_interruption.py` — end-to-end native-fade tests (false-positive on first step gone; real intervention still detected; software unchanged).

**Conventions:** Run a single test with `pytest tests/<file>::<Class>::<test> -p no:xdist -q`. Run a file with `pytest tests/<file> -q`. After code changes, `ruff check . && ruff format . && npx pyright`.

---

### Task 1: `FadeChange` hybrid-aware anchor accessors

**Files:**
- Modify: `custom_components/fado/fade_change.py` (add properties to `FadeChange`, after the `has_fade` property ~line 752)
- Test: `tests/test_fade_change.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fade_change.py` (top of file already imports from the module; add `FadeChange` if not present):

```python
from custom_components.fado.fade_change import FadeChange


class TestFadeChangeAnchors:
    """Per-dimension 'fade from' anchors used to seed native-transition matching."""

    def test_anchor_brightness_is_start_brightness(self) -> None:
        fade = FadeChange(start_brightness=76, end_brightness=0)
        assert fade.anchor_brightness == 76

    def test_anchor_brightness_none_when_not_fading_brightness(self) -> None:
        fade = FadeChange(start_hs=(100.0, 50.0), end_hs=(150.0, 80.0))
        assert fade.anchor_brightness is None

    def test_anchor_hs_non_hybrid_is_start_hs(self) -> None:
        fade = FadeChange(start_hs=(100.0, 50.0), end_hs=(150.0, 80.0))
        assert fade.anchor_hs == (100.0, 50.0)

    def test_anchor_color_temp_non_hybrid_is_kelvin_of_start_mireds(self) -> None:
        # 250 mireds -> 4000 K
        fade = FadeChange(start_mireds=250, end_mireds=400)
        assert fade.anchor_color_temp_kelvin == 4000

    def test_anchor_color_temp_none_when_not_fading_color_temp(self) -> None:
        fade = FadeChange(start_brightness=10, end_brightness=200)
        assert fade.anchor_color_temp_kelvin is None

    def test_anchor_hs_hybrid_mireds_to_hs_uses_crossover(self) -> None:
        # HS is phase 2: anchor is the crossover HS, not start_hs (which is None).
        fade = FadeChange(
            start_mireds=250,
            end_hs=(150.0, 80.0),
            hybrid_direction="mireds_to_hs",
            _crossover_hs=(40.0, 12.0),
            _crossover_mireds=286,
        )
        assert fade.anchor_hs == (40.0, 12.0)

    def test_anchor_color_temp_hybrid_hs_to_mireds_uses_crossover(self) -> None:
        # color_temp is phase 2: anchor is kelvin(crossover_mireds); start_mireds is None.
        # 286 mireds -> 3496 K (int(1_000_000/286)).
        fade = FadeChange(
            start_hs=(100.0, 50.0),
            end_mireds=400,
            hybrid_direction="hs_to_mireds",
            _crossover_hs=(40.0, 12.0),
            _crossover_mireds=286,
        )
        assert fade.anchor_color_temp_kelvin == 3496
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_fade_change.py::TestFadeChangeAnchors -p no:xdist -q`
Expected: FAIL with `AttributeError: 'FadeChange' object has no attribute 'anchor_brightness'`.

- [ ] **Step 3: Implement the accessors**

In `custom_components/fado/fade_change.py`, add immediately after the `has_fade` property (the `@property def has_fade` block, ~line 745-752):

```python
    @property
    def anchor_brightness(self) -> int | None:
        """Brightness the device fades from (spans the whole fade, incl. hybrid)."""
        return self.start_brightness

    @property
    def anchor_hs(self) -> tuple[float, float] | None:
        """HS the device fades from. Phase 2 of a mireds->HS hybrid starts at the crossover."""
        if self.hybrid_direction == "mireds_to_hs":
            return self._crossover_hs
        return self.start_hs

    @property
    def anchor_color_temp_kelvin(self) -> int | None:
        """Color temp (kelvin) the device fades from. Phase 2 of an HS->mireds hybrid
        starts at the crossover."""
        if self.hybrid_direction == "hs_to_mireds":
            mireds = self._crossover_mireds
        else:
            mireds = self.start_mireds
        return _mireds_to_kelvin(mireds) if mireds is not None else None
```

(`_mireds_to_kelvin` already exists at module scope in this file, ~line 60.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_fade_change.py::TestFadeChangeAnchors -p no:xdist -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/fade_change.py tests/test_fade_change.py
git commit -m "feat: add hybrid-aware fade anchor accessors to FadeChange"
```

---

### Task 2: `ExpectedState` moving-anchor state + enable/clear API

**Files:**
- Modify: `custom_components/fado/expected_state.py` (dataclass fields after `_condition` ~line 96; new methods; `wait_and_clear` ~line 452-474)
- Test: `tests/test_expected_state_colors.py`

- [ ] **Step 1: Write the failing tests**

Add a new class to `tests/test_expected_state_colors.py`:

```python
class TestMovingAnchorConfig:
    """Enabling/clearing native-transition moving-anchor mode."""

    def test_set_moving_anchor_seeds_state(self) -> None:
        state = ExpectedState(entity_id="light.test")
        state.set_moving_anchor(brightness=76, hs_color=(100.0, 50.0), color_temp_kelvin=4000)
        assert state.moving_anchor_active is True
        assert state.anchor_brightness == 76
        assert state.anchor_hs == (100.0, 50.0)
        assert state.anchor_color_temp_kelvin == 4000

    def test_set_moving_anchor_defaults_to_none(self) -> None:
        state = ExpectedState(entity_id="light.test")
        state.set_moving_anchor(brightness=76)
        assert state.moving_anchor_active is True
        assert state.anchor_brightness == 76
        assert state.anchor_hs is None
        assert state.anchor_color_temp_kelvin is None

    def test_clear_moving_anchor_resets_state(self) -> None:
        state = ExpectedState(entity_id="light.test")
        state.set_moving_anchor(brightness=76)
        state.clear_moving_anchor()
        assert state.moving_anchor_active is False
        assert state.anchor_brightness is None

    async def test_wait_and_clear_clears_moving_anchor(self) -> None:
        state = ExpectedState(entity_id="light.test")
        state.set_moving_anchor(brightness=76)
        await state.wait_and_clear()
        assert state.moving_anchor_active is False
        assert state.anchor_brightness is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorConfig -p no:xdist -q`
Expected: FAIL with `AttributeError: 'ExpectedState' object has no attribute 'set_moving_anchor'`.

- [ ] **Step 3: Add the fields and methods**

In `custom_components/fado/expected_state.py`, in the `ExpectedState` dataclass, add fields after the `_condition` field (~line 96):

```python
    moving_anchor_active: bool = False
    anchor_brightness: int | None = None
    anchor_hs: tuple[float, float] | None = None
    anchor_color_temp_kelvin: int | None = None
```

Add these methods to the `ExpectedState` class (e.g. just after `add`, ~line 106):

```python
    def set_moving_anchor(
        self,
        *,
        brightness: int | None = None,
        hs_color: tuple[float, float] | None = None,
        color_temp_kelvin: int | None = None,
    ) -> None:
        """Enable native-transition moving-anchor matching, seeded at the fade start.

        While active, each entry's match window uses the live anchor (the last
        reported value) as its 'from' bound instead of the entry's own from_*.
        """
        self.moving_anchor_active = True
        self.anchor_brightness = brightness
        self.anchor_hs = hs_color
        self.anchor_color_temp_kelvin = color_temp_kelvin
        _LOGGER.debug(
            "%s: moving anchor enabled (brightness=%s, hs=%s, kelvin=%s)",
            self.entity_id,
            brightness,
            hs_color,
            color_temp_kelvin,
        )

    def clear_moving_anchor(self) -> None:
        """Disable moving-anchor matching and forget the anchors."""
        self.moving_anchor_active = False
        self.anchor_brightness = None
        self.anchor_hs = None
        self.anchor_color_temp_kelvin = None
```

In `wait_and_clear` (~line 452-474), after `self.values.clear()`, add:

```python
        self.clear_moving_anchor()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorConfig -p no:xdist -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/expected_state.py tests/test_expected_state_colors.py
git commit -m "feat: add moving-anchor state and enable/clear API to ExpectedState"
```

---

### Task 3: Brightness moving-anchor matching + anchor advancement

**Files:**
- Modify: `custom_components/fado/expected_state.py` (`match_and_remove` ~line 187-189; `_brightness_match` ~line 264-309; new `_advance_anchor` helper)
- Test: `tests/test_expected_state_colors.py`

- [ ] **Step 1: Write the failing tests**

Add a new class to `tests/test_expected_state_colors.py`:

```python
class TestMovingAnchorBrightness:
    """Moving-anchor matching for native-transition brightness fades."""

    def test_replays_logged_false_positive_without_flagging(self) -> None:
        """The reported bug: lagging/coalesced reports must NOT be 'no match'."""
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(brightness=76)  # fade start
        es.add(ExpectedValues(brightness=60))  # step 1 target
        es.add(ExpectedValues(brightness=46))  # step 2 target

        # Device lags: reports 71 (between real start 76 and first target 60).
        m1 = es.match_and_remove(ExpectedValues(brightness=71), old=ExpectedValues(brightness=76))
        assert m1 is not None
        assert es.anchor_brightness == 71  # anchor advanced to last report

        # Next report coalesces past the 60 step straight to 46.
        m2 = es.match_and_remove(ExpectedValues(brightness=46), old=ExpectedValues(brightness=71))
        assert m2 is not None
        assert es.anchor_brightness == 46
        assert es.is_empty  # exact at 46 drained both entries

    def test_first_step_intermediate_matches_via_anchor(self) -> None:
        """First step (no from_brightness) still accepts an intermediate via the anchor."""
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(brightness=76)
        es.add(ExpectedValues(brightness=60))  # only one step commanded so far

        m = es.match_and_remove(ExpectedValues(brightness=71), old=ExpectedValues(brightness=76))
        assert m is not None  # would be None under old point-match-only first step

    def test_moving_anchor_tightens_window_and_detects_bump(self) -> None:
        """The headline: a bump back up that the fade-start band would accept is flagged."""
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(brightness=100)
        es.add(ExpectedValues(brightness=40))  # down-fade target

        assert (
            es.match_and_remove(ExpectedValues(brightness=50), old=ExpectedValues(brightness=100))
            is not None
        )
        assert es.anchor_brightness == 50

        # 80 is inside the original [40,100] band but outside the tightened [40,50] window.
        assert (
            es.match_and_remove(ExpectedValues(brightness=80), old=ExpectedValues(brightness=50))
            is None
        )
        assert es.anchor_brightness == 50  # anchor NOT advanced on no-match

    def test_dim_ahead_below_lowest_target_detected(self) -> None:
        """A jump below the furthest commanded target is flagged."""
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(brightness=100)
        es.add(ExpectedValues(brightness=60))
        es.add(ExpectedValues(brightness=46))

        # Device at 71, then user jumps down to 30 (below lowest target 46).
        assert (
            es.match_and_remove(ExpectedValues(brightness=71), old=ExpectedValues(brightness=100))
            is not None
        )
        assert (
            es.match_and_remove(ExpectedValues(brightness=30), old=ExpectedValues(brightness=71))
            is None
        )

    def test_jitter_within_tolerance_not_flagged(self) -> None:
        """A small in-direction bounce within tolerance still matches."""
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(brightness=100)
        es.add(ExpectedValues(brightness=40))

        assert (
            es.match_and_remove(ExpectedValues(brightness=50), old=ExpectedValues(brightness=100))
            is not None
        )
        # 52 is 2 above the anchor 50 — within BRIGHTNESS_TOLERANCE (3).
        assert (
            es.match_and_remove(ExpectedValues(brightness=52), old=ExpectedValues(brightness=50))
            is not None
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorBrightness -p no:xdist -q`
Expected: FAIL — `test_replays_logged_false_positive_without_flagging` returns `None` for `m1` (entries have no `from_brightness`, so point-match-only rejects 71).

- [ ] **Step 3: Implement anchor-based brightness matching + advancement**

In `custom_components/fado/expected_state.py`, replace the body of `_brightness_match` (~line 264-309) with:

```python
    def _brightness_match(
        self,
        expected: ExpectedValues,
        actual: ExpectedValues,
        old: ExpectedValues | None,
    ) -> str | None:
        """Check if brightness matches. Returns match type or None."""
        if actual.brightness is None or expected.brightness is None:
            return None

        # Native transitions: window 'from' bound is the live anchor (last reported
        # value), shared across steps. Otherwise fall back to the entry's own
        # from_brightness (legacy per-step range path / software stepping).
        range_from = (
            self.anchor_brightness if self.moving_anchor_active else expected.from_brightness
        )

        if range_from is not None:
            min_val = min(range_from, expected.brightness)
            max_val = max(range_from, expected.brightness)
            if not (
                old is not None
                and old.brightness is not None
                and min_val - BRIGHTNESS_TOLERANCE
                <= old.brightness
                <= max_val + BRIGHTNESS_TOLERANCE
            ):
                return None

            # Exact match (target within tolerance)
            if expected.brightness == 0:
                if actual.brightness == 0:
                    return "exact"
            elif abs(expected.brightness - actual.brightness) <= BRIGHTNESS_TOLERANCE:
                return "exact"

            # Range match (intermediate value)
            if min_val <= actual.brightness <= max_val:
                return "range"

            return None

        # Point match (no transition range — just check target with tolerance)
        if expected.brightness == 0:
            if actual.brightness == 0:
                return "exact"
        elif abs(expected.brightness - actual.brightness) <= BRIGHTNESS_TOLERANCE:
            return "exact"

        return None
```

Add this helper to the `ExpectedState` class (e.g. just after `_brightness_match`):

```python
    def _advance_anchor(self, matched: ExpectedValues, actual: ExpectedValues) -> None:
        """Advance each tracked dimension's anchor to the latest reported value."""
        if matched.brightness is not None and actual.brightness is not None:
            self.anchor_brightness = actual.brightness
        if matched.hs_color is not None and actual.hs_color is not None:
            self.anchor_hs = actual.hs_color
        if matched.color_temp_kelvin is not None and actual.color_temp_kelvin is not None:
            self.anchor_color_temp_kelvin = actual.color_temp_kelvin
```

In `match_and_remove`, right after the "no match" early return (~line 187-189, the block that returns `None` when `matched_index is None`), insert the advancement before the exact/range removal logic:

```python
        if matched_index is None or matched_value is None or match_type is None:
            _LOGGER.debug("%s: -> no match found", self.entity_id)
            return None

        # Advance the moving anchor to the reported value (matched reports only).
        if self.moving_anchor_active:
            self._advance_anchor(matched_value, actual)

        # Only remove on exact match (final value reached)
        if match_type == "exact":
            ...
```

(Leave the existing exact/range removal block below unchanged.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorBrightness -p no:xdist -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the existing matching tests to confirm no regression**

Run: `pytest tests/test_expected_state_colors.py -p no:xdist -q`
Expected: PASS (all existing point/range/old-state tests still green — they never enable moving-anchor mode, so they take the `expected.from_brightness` fallback path).

- [ ] **Step 6: Commit**

```bash
git add custom_components/fado/expected_state.py tests/test_expected_state_colors.py
git commit -m "feat: brightness moving-anchor matching for native transitions"
```

---

### Task 4: Color-temp (kelvin) moving-anchor matching

**Files:**
- Modify: `custom_components/fado/expected_state.py` (`_kelvin_match` ~line 408-445)
- Test: `tests/test_expected_state_colors.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_expected_state_colors.py`:

```python
class TestMovingAnchorKelvin:
    """Moving-anchor matching for native-transition color-temp fades."""

    def test_lagging_kelvin_reports_match(self) -> None:
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(color_temp_kelvin=2700)  # fade start
        es.add(ExpectedValues(color_temp_kelvin=4000))  # step 1 target
        es.add(ExpectedValues(color_temp_kelvin=6500))  # step 2 (final) target

        m1 = es.match_and_remove(
            ExpectedValues(color_temp_kelvin=3500), old=ExpectedValues(color_temp_kelvin=2700)
        )
        assert m1 is not None
        assert es.anchor_color_temp_kelvin == 3500

        m2 = es.match_and_remove(
            ExpectedValues(color_temp_kelvin=6500), old=ExpectedValues(color_temp_kelvin=3500)
        )
        assert m2 is not None
        assert es.is_empty

    def test_kelvin_against_direction_bump_detected(self) -> None:
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(color_temp_kelvin=2700)
        es.add(ExpectedValues(color_temp_kelvin=6500))

        assert (
            es.match_and_remove(
                ExpectedValues(color_temp_kelvin=4000), old=ExpectedValues(color_temp_kelvin=2700)
            )
            is not None
        )
        # Jump back below the tightened window [4000, 6500] -> manual.
        assert (
            es.match_and_remove(
                ExpectedValues(color_temp_kelvin=3000), old=ExpectedValues(color_temp_kelvin=4000)
            )
            is None
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorKelvin -p no:xdist -q`
Expected: FAIL — `m1` is `None` (entries have no `from_color_temp_kelvin`, point-match-only rejects 3500).

- [ ] **Step 3: Implement anchor-based kelvin matching**

In `custom_components/fado/expected_state.py`, replace the body of `_kelvin_match` (~line 408-445) with:

```python
    def _kelvin_match(
        self,
        expected: ExpectedValues,
        actual: ExpectedValues,
        old: ExpectedValues | None,
    ) -> str | None:
        """Check if color temp kelvin matches. Returns match type or None."""
        if actual.color_temp_kelvin is None or expected.color_temp_kelvin is None:
            return None

        range_from = (
            self.anchor_color_temp_kelvin
            if self.moving_anchor_active
            else expected.from_color_temp_kelvin
        )

        if range_from is not None:
            min_val = min(range_from, expected.color_temp_kelvin)
            max_val = max(range_from, expected.color_temp_kelvin)
            if not (
                old is not None
                and old.color_temp_kelvin is not None
                and min_val - KELVIN_TOLERANCE
                <= old.color_temp_kelvin
                <= max_val + KELVIN_TOLERANCE
            ):
                return None

            # Exact match (target within tolerance)
            if abs(expected.color_temp_kelvin - actual.color_temp_kelvin) <= KELVIN_TOLERANCE:
                return "exact"

            # Range match (intermediate value)
            if min_val <= actual.color_temp_kelvin <= max_val:
                return "range"

            return None

        # Point match (no transition range)
        if abs(expected.color_temp_kelvin - actual.color_temp_kelvin) <= KELVIN_TOLERANCE:
            return "exact"

        return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorKelvin -p no:xdist -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/expected_state.py tests/test_expected_state_colors.py
git commit -m "feat: color-temp moving-anchor matching for native transitions"
```

---

### Task 5: HS color moving-anchor matching

**Files:**
- Modify: `custom_components/fado/expected_state.py` (`_hs_match` ~line 311-350)
- Test: `tests/test_expected_state_colors.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_expected_state_colors.py`:

```python
class TestMovingAnchorHs:
    """Moving-anchor matching for native-transition HS color fades."""

    def test_lagging_hs_reports_match(self) -> None:
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(hs_color=(100.0, 50.0))  # fade start
        es.add(ExpectedValues(hs_color=(125.0, 65.0)))  # step 1 target
        es.add(ExpectedValues(hs_color=(150.0, 80.0)))  # step 2 (final) target

        m1 = es.match_and_remove(
            ExpectedValues(hs_color=(110.0, 55.0)), old=ExpectedValues(hs_color=(100.0, 50.0))
        )
        assert m1 is not None
        assert es.anchor_hs == (110.0, 55.0)

        m2 = es.match_and_remove(
            ExpectedValues(hs_color=(150.0, 80.0)), old=ExpectedValues(hs_color=(110.0, 55.0))
        )
        assert m2 is not None
        assert es.is_empty

    def test_hs_off_trajectory_report_detected(self) -> None:
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(hs_color=(100.0, 50.0))
        es.add(ExpectedValues(hs_color=(150.0, 80.0)))

        # A wildly different colour (unrelated) is not on the trajectory -> manual.
        m = es.match_and_remove(
            ExpectedValues(hs_color=(300.0, 90.0)), old=ExpectedValues(hs_color=(100.0, 50.0))
        )
        assert m is None

    def test_hs_wraparound_lagging_report_matches(self) -> None:
        es = ExpectedState(entity_id="light.test")
        es.set_moving_anchor(hs_color=(350.0, 50.0))  # fade start near 360
        es.add(ExpectedValues(hs_color=(10.0, 50.0)))  # target wraps past 0

        # Intermediate 355 is on the short wraparound arc.
        m = es.match_and_remove(
            ExpectedValues(hs_color=(355.0, 50.0)), old=ExpectedValues(hs_color=(350.0, 50.0))
        )
        assert m is not None
        assert es.anchor_hs == (355.0, 50.0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorHs -p no:xdist -q`
Expected: FAIL — `m1` is `None` (entries have no `from_hs_color`, point-match-only rejects (110,55)).

- [ ] **Step 3: Implement anchor-based HS matching**

In `custom_components/fado/expected_state.py`, replace the body of `_hs_match` (~line 311-350) with:

```python
    def _hs_match(
        self,
        expected: ExpectedValues,
        actual: ExpectedValues,
        old: ExpectedValues | None,
    ) -> str | None:
        """Check if HS color matches. Returns match type or None."""
        if actual.hs_color is None or expected.hs_color is None:
            return None

        range_from = self.anchor_hs if self.moving_anchor_active else expected.from_hs_color

        if range_from is not None:
            if not (
                old is not None
                and old.hs_color is not None
                and self._hs_range_match(
                    range_from,
                    expected.hs_color,
                    old.hs_color,
                    hue_tolerance=HUE_TOLERANCE,
                    sat_tolerance=SATURATION_TOLERANCE,
                )
            ):
                return None

            # Exact match (target within tolerance)
            if self._hs_exact_match(expected.hs_color, actual.hs_color):
                return "exact"

            # Range match (intermediate value)
            if self._hs_range_match(range_from, expected.hs_color, actual.hs_color):
                return "range"

            return None

        # Point match (no transition range)
        if self._hs_exact_match(expected.hs_color, actual.hs_color):
            return "exact"

        return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_expected_state_colors.py::TestMovingAnchorHs -p no:xdist -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full matching suite to confirm no regression**

Run: `pytest tests/test_expected_state_colors.py tests/test_manual_intervention_colors.py -p no:xdist -q`
Expected: PASS (all green).

- [ ] **Step 6: Commit**

```bash
git add custom_components/fado/expected_state.py tests/test_expected_state_colors.py
git commit -m "feat: HS moving-anchor matching for native transitions"
```

---

### Task 6: Coordinator wiring — enable moving anchor for native fades

**Files:**
- Modify: `custom_components/fado/coordinator.py` (`_run_fade_loop` ~line 363-394; new `_configure_moving_anchor` helper near `_add_expected_values` ~line 877)
- Test: `tests/test_manual_interruption.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_manual_interruption.py` (the `service_calls` fixture and imports already exist in this file):

```python
async def test_native_transition_first_step_intermediates_no_false_intervention(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service_calls: list[ServiceCall],
) -> None:
    """Intermediate reports during the FIRST native step must not be flagged.

    The old design point-matched the first step (no prev_step), so an intermediate
    value reported while the device ramps from its real start to the first target
    was treated as manual intervention. The moving anchor fixes this.
    """
    entity_id = "light.test_first_step"
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_BRIGHTNESS: 200, ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
    )
    hass.data[DOMAIN].data[entity_id] = {"native_transitions": True, "min_delay_ms": 150}

    async def mock_turn_on_with_intermediates(call: ServiceCall) -> None:
        service_calls.append(call)
        eid = call.data.get(ATTR_ENTITY_ID)
        if eid == entity_id and ATTR_BRIGHTNESS in call.data:
            target = call.data[ATTR_BRIGHTNESS]
            current_state = hass.states.get(entity_id)
            current = current_state.attributes.get(ATTR_BRIGHTNESS, 200) if current_state else 200
            # Inject a lagging intermediate on EVERY step, including the first.
            step = (target - current) / 3
            for i in range(1, 3):
                intermediate = int(current + step * i)
                hass.states.async_set(
                    entity_id,
                    STATE_ON,
                    {ATTR_BRIGHTNESS: intermediate, ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
                    context=call.context,
                )
                await asyncio.sleep(0.02)
            hass.states.async_set(
                entity_id,
                STATE_ON,
                {ATTR_BRIGHTNESS: target, ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
                context=call.context,
            )

    hass.services.async_remove("light", "turn_on")
    hass.services.async_register("light", "turn_on", mock_turn_on_with_intermediates)

    fade_task = asyncio.create_task(
        hass.services.async_call(
            DOMAIN,
            SERVICE_FADE_LIGHTS,
            {"entity_id": entity_id, "brightness_pct": 5, "transition": 1.0},
            blocking=True,
        )
    )
    await fade_task

    coordinator: FadeCoordinator = hass.data[DOMAIN]
    entity = coordinator.get_entity(entity_id)
    assert entity is None or not entity.intended_queue, (
        "First-step intermediates should not trigger manual intervention"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_manual_interruption.py::test_native_transition_first_step_intermediates_no_false_intervention -p no:xdist -q`
Expected: FAIL — `entity.intended_queue` is non-empty (first-step intermediate flagged as manual intervention; moving anchor not yet enabled by the coordinator).

- [ ] **Step 3: Add the coordinator helper and call it**

In `custom_components/fado/coordinator.py`, add a helper near `_add_expected_values` (~line 877). It ensures `ExpectedState` exists, then enables (native) or clears (software) moving-anchor mode:

```python
    def _configure_moving_anchor(
        self, entity_id: str, fade: FadeChange, native_transitions: bool
    ) -> None:
        """Enable moving-anchor matching for native fades; clear it otherwise.

        Seeds per-dimension anchors from the fade's start values so the first
        step has a window (not a point) and lagging/coalesced device reports match.
        """
        ent = self.get_or_create_entity(entity_id)
        if native_transitions:
            if ent.expected_state is None:
                ent.expected_state = ExpectedState(entity_id=entity_id)
            ent.expected_state.set_moving_anchor(
                brightness=fade.anchor_brightness,
                hs_color=fade.anchor_hs,
                color_temp_kelvin=fade.anchor_color_temp_kelvin,
            )
        elif ent.expected_state is not None:
            ent.expected_state.clear_moving_anchor()
```

In `_run_fade_loop` (~line 363-394), add the configure call at the very start of the method body, before `delay_ms = fade.delay_ms()`:

```python
        self._configure_moving_anchor(entity_id, fade, native_transitions)
        delay_ms = fade.delay_ms()
        prev_step: FadeStep | None = None
```

(`FadeChange` and `ExpectedState` are already imported in `coordinator.py` — lines ~50.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_manual_interruption.py::test_native_transition_first_step_intermediates_no_false_intervention -p no:xdist -q`
Expected: PASS.

- [ ] **Step 5: Run the existing native + manual tests to confirm no regression**

Run: `pytest tests/test_manual_interruption.py tests/test_fade_execution.py -p no:xdist -q`
Expected: PASS — including `test_native_transition_no_false_intervention`, `test_native_transition_detects_real_intervention`, and the software-stepping manual tests (`test_manual_brightness_change_cancels_fade` etc.).

- [ ] **Step 6: Commit**

```bash
git add custom_components/fado/coordinator.py tests/test_manual_interruption.py
git commit -m "feat: enable moving-anchor matching for native-transition fades"
```

---

### Task 7: Full verification — suite, lint, types

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: PASS (entire suite green). If a previously-passing native test now fails, investigate before proceeding — do not weaken assertions to make them pass.

- [ ] **Step 2: Lint and format**

Run: `ruff check . && ruff format .`
Expected: no errors; formatting clean (commit any formatting changes).

- [ ] **Step 3: Type-check**

Run: `npx pyright`
Expected: no new errors in `expected_state.py`, `coordinator.py`, `fade_change.py`.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "chore: lint/format/type fixups for moving-anchor matching"
```

---

## Self-Review

**Spec coverage:**
- Eliminate native false positive (brightness/HS/kelvin) → Tasks 3, 4, 5 (unit) + Task 6 (end-to-end). ✓
- Preserve & tighten manual detection → `test_moving_anchor_tightens_window_and_detects_bump`, `test_dim_ahead_below_lowest_target_detected`, `test_kelvin_against_direction_bump_detected`, `test_hs_off_trajectory_report_detected`, existing `test_native_transition_detects_real_intervention`. ✓
- Software stepping unchanged → fallback to `expected.from_*` when `moving_anchor_active` is False; Task 3 Step 5 + Task 6 Step 5 regression runs. ✓
- Per-step entries / hybrid / flush unchanged → `_track_and_apply_step` untouched; anchors seeded hybrid-aware via Task 1 accessors. ✓
- Anchor seeded at fade start; reset on clear → Task 2 (`wait_and_clear`) + Task 6 (`_configure_moving_anchor` runs each fade, clearing for software). ✓
- Accepted trade-off (within-band in-direction change invisible) → documented in spec; not a task. ✓

**Placeholder scan:** none.

**Type/name consistency:** `set_moving_anchor`/`clear_moving_anchor`/`moving_anchor_active`/`anchor_brightness`/`anchor_hs`/`anchor_color_temp_kelvin`/`_advance_anchor`/`_configure_moving_anchor` and the `FadeChange` accessors `anchor_brightness`/`anchor_hs`/`anchor_color_temp_kelvin` are used consistently across Tasks 1, 2, 3, 4, 5, 6.
