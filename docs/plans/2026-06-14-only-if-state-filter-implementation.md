# `only_if` State Filter for `fado.fade_lights` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `only_if` parameter to `fado.fade_lights` that restricts the fade to targeted lights whose current power state matches `on` or `off`; unset/null keeps today's "fade everything" behaviour.

**Architecture:** A normalising voluptuous validator (`_normalize_only_if`) accepts the string forms *and* the YAML-boolean forms (`only_if: on` → `True`), mapping to `"on"`/`"off"`/`None`. The value rides on `FadeParams.only_if` and is applied in `FadeCoordinator._resolve_fade_targets`, which already iterates expanded entities and reads `state.state`.

**Tech Stack:** Python 3.13, Home Assistant custom component, voluptuous, pytest (`pytest-homeassistant-custom-component`), ruff, pyright.

**Design doc:** `docs/plans/2026-06-14-only-if-state-filter-design.md`

---

## Context

**Working directory:** `/Users/clintongormley/workspace/worktrees/fado-target`
**Branch:** `target`
**Test command:** `python -m pytest tests/ -q`
**Lint command:** `ruff check . && ruff format --check .`
**Type check:** `npx pyright`

**Key files:**
- `custom_components/fado/const.py` — service attribute constants
- `custom_components/fado/__init__.py` — `FADE_LIGHTS_SCHEMA` and shared validators
- `custom_components/fado/fade_params.py` — `FadeParams` dataclass + `from_service_data`
- `custom_components/fado/coordinator.py` — `_resolve_fade_targets` (line ~145)
- `custom_components/fado/services.yaml` — UI form
- `custom_components/fado/strings.json`, `custom_components/fado/translations/en.json` — field labels
- `README.md` — `fado.fade_lights` usage docs
- `tests/test_only_if.py` — **new** test file for this feature

**Conventions confirmed from the codebase:**
- `FADE_LIGHTS_SCHEMA` is built with `cv.make_entity_service_schema`, which appends a `_HAS_ENTITY_SERVICE_FIELD` validator — so any direct schema test **must include an `entity_id`** or it fails with "must contain at least one of entity_id…".
- `_resolve_fade_targets(call, fade_params)` already receives a `FadeParams`; no signature change needed.
- Test fixtures in `tests/conftest.py`: `mock_light_entity` (on, brightness 200), `mock_light_off` (off), `init_integration`, `captured_calls`.
- Translations: `check_translations.py` treats **missing** keys as warnings (fine) and **stale** keys as errors. Only update `strings.json` + `en.json`.

---

## Task 1: Constant + normalising validator, wired into the schema

**Files:**
- Modify: `custom_components/fado/const.py`
- Modify: `custom_components/fado/__init__.py`
- Test: `tests/test_only_if.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_only_if.py`. The import block below is the **complete** set of
imports the whole file needs across all tasks — add it once now (some names are
only used by Task 2/3 classes appended later; that is fine, lint runs only in
Task 6 by which point everything is used):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_only_if.py -q`
Expected: FAIL — `ImportError: cannot import name '_normalize_only_if'` (and `ATTR_ONLY_IF`).

- [ ] **Step 3: Add the constant**

In `custom_components/fado/const.py`, add to the "Service attributes" block (after `ATTR_EASING = "easing"`):

```python
ATTR_ONLY_IF = "only_if"
```

- [ ] **Step 4: Add the validator and wire it into the schema**

In `custom_components/fado/__init__.py`:

Add `STATE_OFF, STATE_ON` to the existing `homeassistant.const` import (it currently imports `EVENT_HOMEASSISTANT_STARTED`):

```python
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_OFF, STATE_ON
```

Add `ATTR_ONLY_IF` to the `from .const import (...)` block (keep alphabetical-ish with the other `ATTR_*` entries, e.g. after `ATTR_HS_COLOR`):

```python
    ATTR_ONLY_IF,
```

Define the validator just above `# Shared validators for reuse in main and from: schemas` (i.e. before `_BRIGHTNESS_PCT`):

```python
def _normalize_only_if(value: object) -> str | None:
    """Normalise the only_if target filter.

    Accepts the YAML-boolean forms (bare `on`/`off` parse as True/False) as well
    as the string forms, so `only_if: on` works unquoted in automations. None/null
    passes through as "no filter".
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return STATE_ON if value else STATE_OFF
    if isinstance(value, str) and value.lower() in (STATE_ON, STATE_OFF):
        return value.lower()
    raise vol.Invalid(f"only_if must be one of: on, off (got {value!r})")
```

Add the field to `FADE_LIGHTS_SCHEMA` (inside the dict passed to `cv.make_entity_service_schema`, e.g. right after the `ATTR_EASING` line):

```python
        vol.Optional(ATTR_ONLY_IF): _normalize_only_if,
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_only_if.py -q`
Expected: PASS (all `TestNormalizeOnlyIf` + `TestSchemaWiring` tests).

- [ ] **Step 6: Commit**

```bash
git add custom_components/fado/const.py custom_components/fado/__init__.py tests/test_only_if.py
git commit -m "feat: add only_if validator + schema field for fade_lights"
```

---

## Task 2: Plumb `only_if` through `FadeParams`

**Files:**
- Modify: `custom_components/fado/fade_params.py`
- Test: `tests/test_only_if.py` (append)

- [ ] **Step 1: Write the failing tests**

Append this class to the end of `tests/test_only_if.py` (no new imports — they
were all added in Task 1):

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_only_if.py::TestFadeParamsOnlyIf -q`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'only_if'` is not raised yet, instead `AttributeError: 'FadeParams' object has no attribute 'only_if'`.

- [ ] **Step 3: Add the field and parsing**

In `custom_components/fado/fade_params.py`:

Add `ATTR_ONLY_IF` to the `from .const import (...)` block (after `ATTR_HS_COLOR`):

```python
    ATTR_ONLY_IF,
```

Add the field to the dataclass (after `easing: str = "auto"`):

```python
    only_if: str | None = None  # Target filter by current power state: "on"/"off"/None
```

In `from_service_data`, after the `easing = str(...)` line, read the value:

```python
        only_if = data.get(ATTR_ONLY_IF)
```

And pass it into the `return cls(...)` call (add as a keyword argument, e.g. after `easing=easing,`):

```python
            only_if=only_if,
```

Note: `has_target()` and `has_from_target()` are intentionally left unchanged — `only_if` is a filter, not a target.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_only_if.py::TestFadeParamsOnlyIf -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/fade_params.py tests/test_only_if.py
git commit -m "feat: carry only_if filter on FadeParams"
```

---

## Task 3: Apply the filter in `_resolve_fade_targets`

**Files:**
- Modify: `custom_components/fado/coordinator.py`
- Test: `tests/test_only_if.py` (append)

- [ ] **Step 1: Write the failing tests**

Append this class to the end of `tests/test_only_if.py` (no new imports — they
were all added in Task 1):

```python
class TestResolveTargetsOnlyIf:
    """_resolve_fade_targets honours only_if. Uses an end-to-end service call so
    the real targeting/expansion path runs."""

    async def _faded_entities(
        self, hass: HomeAssistant, target_ids: list[str], only_if: object
    ) -> set[str]:
        """Call fade_lights with the given target + only_if, return faded entity ids."""
        data: dict = {"brightness_pct": 50}
        if only_if is not None:
            data[ATTR_ONLY_IF] = only_if
        with patch(
            "custom_components.fado.coordinator.FadeCoordinator._fade_light",
            new_callable=AsyncMock,
        ) as mock_fade:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FADE_LIGHTS,
                data,
                target={"entity_id": target_ids},
                blocking=True,
            )
            await hass.async_block_till_done()
        return {c.args[0] for c in mock_fade.call_args_list}

    async def test_only_if_on_keeps_only_on_lights(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,  # on
        mock_light_off: str,  # off
    ) -> None:
        faded = await self._faded_entities(
            hass, [mock_light_entity, mock_light_off], "on"
        )
        assert faded == {mock_light_entity}

    async def test_only_if_off_keeps_only_off_lights(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
        mock_light_off: str,
    ) -> None:
        faded = await self._faded_entities(
            hass, [mock_light_entity, mock_light_off], "off"
        )
        assert faded == {mock_light_off}

    async def test_unset_only_if_keeps_all_lights(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
        mock_light_off: str,
    ) -> None:
        faded = await self._faded_entities(
            hass, [mock_light_entity, mock_light_off], None
        )
        assert faded == {mock_light_entity, mock_light_off}

    async def test_only_if_on_excludes_unknown_state(
        self,
        hass: HomeAssistant,
        init_integration: MockConfigEntry,
        mock_light_entity: str,
    ) -> None:
        hass.states.async_set(
            "light.unknown_state",
            "unknown",
            {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]},
        )
        faded = await self._faded_entities(
            hass, [mock_light_entity, "light.unknown_state"], "on"
        )
        assert faded == {mock_light_entity}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_only_if.py::TestResolveTargetsOnlyIf -q`
Expected: FAIL — `test_only_if_on_keeps_only_on_lights` / `off` / `unknown` fail because the off (and unknown) light is still faded (filter not applied yet). `test_unset_only_if_keeps_all_lights` passes already.

- [ ] **Step 3: Apply the filter**

In `custom_components/fado/coordinator.py`, inside `_resolve_fade_targets`, add the state-filter check immediately after the unavailable check and before `_can_apply_fade_params`. The loop currently reads:

```python
        for entity_id in expanded_entities:
            state = self.hass.states.get(entity_id)
            if not state or state.state == "unavailable":
                _LOGGER.debug("%s: Skipping - entity unavailable", entity_id)
                continue
            if not _can_apply_fade_params(state, fade_params):
```

Insert between the two `if` blocks:

```python
            if fade_params.only_if is not None and state.state != fade_params.only_if:
                _LOGGER.debug(
                    "%s: Skipping - state %s does not match only_if=%s",
                    entity_id,
                    state.state,
                    fade_params.only_if,
                )
                continue
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_only_if.py -q`
Expected: PASS (entire file).

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `python -m pytest tests/ -q`
Expected: PASS (no regressions; `_resolve_fade_targets` change is additive and guarded by `only_if is not None`).

- [ ] **Step 6: Commit**

```bash
git add custom_components/fado/coordinator.py tests/test_only_if.py
git commit -m "feat: filter fade targets by current state via only_if"
```

---

## Task 4: UI form + translations

**Files:**
- Modify: `custom_components/fado/services.yaml`
- Modify: `custom_components/fado/strings.json`
- Modify: `custom_components/fado/translations/en.json`

- [ ] **Step 1: Add the field to `services.yaml`**

In `custom_components/fado/services.yaml`, under `fade_lights: advanced_fields: fields:`, add `only_if` after the `brightness:` field (the last field in that block). Match the existing indentation (8 spaces for the field key). Do **not** add a `supported_color_modes` filter — it applies to any light:

```yaml
        only_if:
          name: Only if state
          description: >-
            Only fade lights currently in this state. 'On' affects only lights
            that are already on; 'off' affects only lights that are off. Leave
            unset to fade all targeted lights.
          example: "on"
          selector:
            select:
              options:
                - label: "On (only lights currently on)"
                  value: "on"
                - label: "Off (only lights currently off)"
                  value: "off"
```

- [ ] **Step 2: Add the string to `strings.json`**

In `custom_components/fado/strings.json`, under `services.fade_lights.fields`, add (after the `brightness` entry):

```json
        "only_if": {
          "name": "Only if state",
          "description": "Only fade lights currently in this state. 'On' affects only lights that are already on; 'off' affects only lights that are off. Leave unset to fade all targeted lights."
        }
```

(Ensure the preceding entry ends with a comma so the JSON stays valid.)

- [ ] **Step 3: Mirror the string into `translations/en.json`**

Apply the identical `only_if` entry under `services.fade_lights.fields` in `custom_components/fado/translations/en.json`.

- [ ] **Step 4: Verify YAML + JSON parse and translations are consistent**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('custom_components/fado/services.yaml'))" \
  && python -c "import json; json.load(open('custom_components/fado/strings.json')); json.load(open('custom_components/fado/translations/en.json'))" \
  && python scripts/check_translations.py
```
Expected: no exceptions; `check_translations.py` exits 0 (missing keys in the other 24 languages are warnings, not errors).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/services.yaml custom_components/fado/strings.json custom_components/fado/translations/en.json
git commit -m "feat: surface only_if in the fade_lights UI + en strings"
```

---

## Task 5: README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a parameter section**

In `README.md`, in the `## Usage: fado.fade_lights` → `### Parameters` area, add a new `####` section immediately after the "Easing curves" section (which ends at the `ease_in_out_sine` bullet, just before `### Examples:`):

```markdown
#### **State filter** (optional `only_if:`, default: none):

Restrict the fade to lights that are currently in a given state:

- **`on`**: only fade lights that are already on (skip lights that are off)
- **`off`**: only fade lights that are currently off (skip lights that are on)

Leave unset (the default) to fade every targeted light. Lights in any
other state (e.g. `unavailable`, `unknown`) are skipped whenever `only_if`
is set.

> **Note:** In YAML, bare `on`/`off` parse as booleans, but Fado accepts
> them anyway — `only_if: on` and `only_if: "on"` are equivalent.
```

- [ ] **Step 2: Add an example**

After the "Basic fade" example block (ends with its closing ```` ``` ````), add:

```markdown
#### **Dim only the lights that are already on:**

```yaml
action: fado.fade_lights
target:
  area_id: living_room
data:
  brightness_pct: 20
  transition: 5
  only_if: on
```
```

- [ ] **Step 3: Verify the docs guard passes**

Run: `python scripts/check_docs.py origin/main..HEAD`
Expected: exit 0 (README was touched, so no structural-drift block).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document only_if state filter for fade_lights"
```

---

## Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (all tests, including the new `tests/test_only_if.py`).

- [ ] **Step 2: Lint**

Run: `ruff check . && ruff format --check .`
Expected: no errors. The enabled rule set is `E, F, W, I, UP, B, C4, SIM` (note
`I` = isort import ordering). If `ruff check` reports auto-fixable issues
(e.g. `I001` import ordering), run `ruff check --fix .`; if `ruff format --check`
reports diffs, run `ruff format .`. Then re-commit.

- [ ] **Step 3: Type check**

Run: `npx pyright`
Expected: no new errors introduced by these changes.

- [ ] **Step 4: Final commit if lint/format changed anything**

```bash
git add -A
git commit -m "chore: lint/format for only_if filter" || echo "nothing to commit"
```

---

## Self-Review (completed during planning)

**Spec coverage:**
- Behaviour table (on/off/unset) → Task 3 tests. ✅
- YAML-boolean normalisation → Task 1 validator + tests. ✅
- Explicit `null` = no filter → Task 1 (`test_schema_passes_null_through`) + Task 2 (`test_explicit_null_only_if_is_none`). ✅
- `only_if` not a fade target → Task 2 (`test_only_if_does_not_count_as_target`). ✅
- `unknown`-state exclusion → Task 3 (`test_only_if_on_excludes_unknown_state`). ✅
- const / schema / FadeParams / coordinator / services.yaml / strings+en / README → Tasks 1–5. ✅

**Type consistency:** `_normalize_only_if` (Task 1) is the same name imported in tests and referenced when wiring the schema. `ATTR_ONLY_IF` is added in const (Task 1) and imported in `__init__.py` (Task 1) and `fade_params.py` (Task 2). `FadeParams.only_if` (Task 2) is the same attribute read in `_resolve_fade_targets` (Task 3). ✅

**Placeholder scan:** none — every code/edit step contains the actual content. ✅
