# Native-transition manual-intervention false positives: moving-anchor matching

**Date:** 2026-06-14
**Status:** Approved (design)
**Area:** `custom_components/fado/expected_state.py`, `coordinator.py`, `fade_change.py`

## Problem

A single fade command targeting two lights (`light.master_bathroom_seat_lights`
and `light.master_bathroom_shower_lights`) faded both from brightness 76 → 0.
The seat light (`native_transitions=False`) faded correctly. The shower light
(`native_transitions=True`) was repeatedly and **incorrectly** flagged as a
manual intervention, triggering a spurious restore. This happens at least once
a day — effectively every time a native-transition light runs a multi-step fade
with a meaningful brightness change.

### Observed log (trimmed)

```
shower: Fading in 9 steps, (brightness=76->0, easing=ease_out_quad, delay_ms=555.5, native_transitions=True)
shower: add(brightness=60)            # step 1 target → count=1
shower: add(brightness=60->46)        # step 2 target → count=2
shower: match_and_remove (brightness=76->71)  -> no match found
shower: Manual intervention detected (state=on, brightness=76->71)
...
shower: match_and_remove (brightness=71->46)  -> no match found
shower: Manual intervention detected (state=on, brightness=71->46)
```

## Root cause

With native transitions, fado issues a small number of large steps (9 here) and
lets the **device** drive the ramp. The device's state reports **lag and
coalesce** across fado's commanded steps — note `71->46` in the log skips the
commanded `60` step entirely.

fado's expected-state matching models each commanded step as a narrow per-step
window whose lower/"from" bound is the **previous commanded target**:

- `coordinator.py:456` — `from_brightness=prev_step.brightness if prev_step is not None else None`.
  The **first** step therefore has `from_brightness=None`, so it uses
  *point matching* only (`expected_state.py:302-309`): it can match its exact
  target (60 ± `BRIGHTNESS_TOLERANCE=3`) and nothing else.
- For later steps, the **old-state guard** (`expected_state.py:280-287`)
  requires the reported *old* brightness to fall inside that step's narrow
  window `[min−tol, max+tol]`.

Tracing the first failing event (`old=76, new=71`) against the queue
`[(target=60, from=None), (target=46, from=60)]`:

- vs `(60, from=None)` → point match: `|60 − 71| = 11 > 3` → no match. The
  intermediate value 71 (between the real start 76 and the first target 60) has
  no range to fall into, because step 1 carries no `from`.
- vs `(46, from=60)` → range branch, but old-state guard rejects: `76 ∉ [43, 63]`.

No match → false "manual intervention". That first false hit spawns the restore
task; every subsequent transition report is then also flagged (cascade).

The seat light avoids this because `native_transitions=False` produces 50 small
software steps that fado applies itself; reports track each step within ±3 and
point-matching succeeds.

## Goals

- Eliminate the false positive for native-transition fades (brightness, HS
  color, and color temperature).
- **Preserve** — and where possible tighten — genuine manual-intervention
  detection. A whole-fade "accept anything between start and end" band is
  explicitly rejected because it would blind detection.
- Leave software stepping (`native_transitions=False`) behavior byte-for-byte
  unchanged.

## Non-goals

- Detecting a manual change that lands *within* the still-plausible fade band
  and moves in the fade direction (see Trade-off). This is inherent to
  delegating the ramp to the device.
- Changing fade-step generation, easing, or the `NATIVE_TRANSITION_MS` value.

## Design: moving-anchor per-step windows

Keep the existing **per-step entries** and the existing queue / flush /
coalesce machinery. Change only the **"from" bound** of each native entry:
instead of the previous commanded target, use a single shared **anchor** equal
to the **last reported value**, seeded at the fade's start value.

So where today the native queue windows are conceptually

```
[ ]        [x1→x2]   [x2→x3]   [x3→x4]      (from = previous target)
```

they become

```
[y→x1]     [y→x2]    [y→x3]    [y→x4]       (from = y = last reported value)
```

- The **target** bound of each entry is unchanged (the per-step commanded
  value `x_i`). It remains the bound facing the fade end, so the device is not
  permitted to run *past* the furthest target commanded so far.
- The **anchor** `y` is shared across all outstanding entries, seeded to the
  fade's start value, and **advanced to the reported value on every matched
  report**. A manual value (an unmatched report) never moves the anchor.
- The acceptable band at any moment is therefore
  `[lowest-commanded-target … y]` (in the fade direction, ± tolerance) — not
  the whole `[end … start]` band — and it **shrinks as the fade progresses**.

### Worked trace (the log above)

Anchor `y` seeded to 76; targets 60, 46, …

| event      | windows (current `y`)        | result                         | new `y` |
|------------|------------------------------|--------------------------------|---------|
| `76 -> 71` | `[60→76]`, `[46→76]`         | 71 ∈ [60,76] → range (keep)    | **71**  |
| `71 -> 46` | `[60→71]`, `[46→71]`         | 46 hits target 46 → exact, drain | **46**  |
| …          | shrinks each matched report  | …                              | …       |
| `… -> 0`   | `[…→y]`                      | exact at target 0 → flush      | —       |

No false positive. Detection stays tight: while the device sits at `y=71` with
targets down to 46 outstanding, a manual bump to 80 (`> 71`) **and** a jump down
to 30 (`< 46`) both fall outside every window → correctly flagged.

## Mechanics

### State (`ExpectedState`)

Add per-dimension live anchors and a native-mode flag:

- `native_mode: bool` — when true, entries use moving-anchor range matching;
  when false, point matching (unchanged software-stepping path).
- `anchor_brightness: int | None`
- `anchor_hs: tuple[float, float] | None`
- `anchor_color_temp_kelvin: int | None`

A `begin_native(...)` (or equivalent) call sets `native_mode=True` and seeds the
anchors from the fade's per-dimension start values. Anchors and `native_mode`
reset when the expected state is cleared (`wait_and_clear`, and the
`entity_fade_state` reset path at `entity_fade_state.py:153-155`).

### Seeding the anchors (`coordinator.py`)

At native fade start (in `_execute_fade` once `native_transitions` is known,
`coordinator.py:350`), seed the anchors from new **hybrid-aware accessors on
`FadeChange`**:

- `anchor_brightness` → `start_brightness` (brightness spans the whole fade,
  including both hybrid phases).
- `anchor_hs` → non-hybrid: `start_hs`; `hs_to_mireds`: `start_hs` (phase 1);
  `mireds_to_hs`: `crossover_hs` (phase 2).
- `anchor_color_temp_kelvin` → non-hybrid: `kelvin(start_mireds)`;
  `hs_to_mireds`: `kelvin(crossover_mireds)` (phase 2); `mireds_to_hs`:
  `kelvin(start_mireds)` (phase 1).

Seeding all anchors up front is safe even for hybrid: a phase-2 dimension has no
entries until its phase begins, so its anchor simply sits at the phase start
(the value the device will be at when that phase starts) until the first report
advances it.

Per-step registration in `_track_and_apply_step` / `_run_fade_loop` is otherwise
**unchanged** — entries are still added one per step, preserving hybrid handling
and the flush/coalesce logic. Native entries no longer need their `from_*`
bound populated for matching (the live anchor replaces it); `from_*` may be left
unset for native entries, with logging updated to show the live window.

### Matching (`expected_state.py`)

`match_and_remove` gains anchor handling:

- `_brightness_match` / `_kelvin_match`: when `native_mode`, compute the window
  from `[anchor, target]` (via `min`/`max`, so it works for both up- and
  down-fades) instead of from `expected.from_*`. Exact = target within tolerance
  (and the existing `brightness == 0 / actual == 0` special case); range =
  reported value within the window; old-state guard = reported *old* within the
  window ± tolerance. When not `native_mode`, behavior is exactly as today.
- `_hs_match`: same shape, reusing `_hs_range_match` with `anchor_hs` as the
  moving "from" corner and the step's target HS as the other corner. **No arc
  projection / progress-fraction machinery is needed** — the "from = last
  reported HS" rule makes HS uniform with the 1-D dimensions.
- On a successful match (range *or* exact) of the whole entry, update each
  tracked dimension's anchor from `actual` before applying the
  remove/keep logic. Tolerance on the window absorbs device jitter (a small
  reading bounce in the fade direction does not falsely flag).

Direction is implicit in `min`/`max(anchor, target)`; no explicit
direction field is required.

## Manual-intervention semantics & trade-off

- **Detected:** any report outside every outstanding window — i.e. brighter than
  the last reported value (against a down-fade) or beyond the furthest target
  commanded so far (dim-ahead), and symmetrically for up-fades; plus the
  existing off→on / wrong-dimension cases.
- **Not detected (accepted):** a change landing *between* the lowest commanded
  target and the last reported value, moving in the fade direction — it is
  indistinguishable from the device's own ramp. This band shrinks as the fade
  progresses. (Degenerate worst case: a very laggy device for which fado has
  already commanded many steps ahead widens the lower bound toward the fade end;
  in practice ~1–2 steps are outstanding given step spacing vs. report cadence.)

This is strictly better than today (which false-positives constantly) and than a
whole-fade band (which would detect almost nothing).

## Hybrid fades

Per-step registration is retained, so hybrid dimension-switching at the
crossover (`fade_change.py:1039` onward — HS-phase steps emit only `hs_color`,
mireds-phase steps emit only `color_temp_kelvin`, brightness spans both) is
handled exactly as today. The only hybrid-specific addition is the seeding of
the phase-2 dimension's anchor from the crossover value via the `FadeChange`
accessors above.

## Unchanged

- Software stepping (`native_transitions=False`): `native_mode` stays false;
  point matching with `from_*` is untouched. Regression test must confirm the
  seat-light behavior is identical.
- Step generation, easing, flush timing, restore logic.

## Testing (TDD)

Unit tests (in the existing `expected_state` / coordinator test suites):

1. **Regression of the reported bug:** native down-fade 76→0, feed the logged
   coalesced reports (`76→71`, `71→46`, …) → no manual intervention; queue
   drains to empty on reaching 0.
2. **Anchor advances / window tightens:** after matching a report, a subsequent
   report just inside the old (wider) band but outside the tightened band is
   flagged.
3. **Against-direction bump detected:** device at `y`, manual report `> y + tol`
   → manual intervention.
4. **Dim-ahead detected:** report `<` lowest commanded target − tol → manual
   intervention.
5. **Jitter absorbed:** a small in-direction reading bounce within tolerance is
   not flagged.
6. **HS moving anchor:** native HS fade with coalesced intermediate reports →
   matched; an off-trajectory color report → flagged. Include hue-wraparound.
7. **Color-temp moving anchor:** analogous to brightness.
8. **Hybrid:** two-phase fade; phase-1 (HS) reports match, phase-2 (color-temp)
   reports match with the crossover-seeded anchor.
9. **Software stepping unchanged:** existing point-match tests still pass; a
   `native_transitions=False` fade behaves exactly as before.

## Files affected

- `custom_components/fado/expected_state.py` — anchors + `native_mode` state;
  moving-anchor logic in `_brightness_match`, `_kelvin_match`, `_hs_match`;
  anchor update in `match_and_remove`; reset on clear.
- `custom_components/fado/coordinator.py` — seed anchors / enable native mode at
  fade start; native entries no longer set `from_*` as the matching bound.
- `custom_components/fado/fade_change.py` — hybrid-aware per-dimension anchor
  accessors.
- Tests for the above.
