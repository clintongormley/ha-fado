# `only_if` State Filter for `fado.fade_lights` — Design

**Goal:** Add an optional `only_if` parameter to the `fado.fade_lights` action that
restricts the fade to targeted lights whose *current* power state matches `on` or
`off`. Default (unset / null) preserves today's behaviour: fade every targeted light.

**Status:** Approved (2026-06-14)

---

## Behaviour

| `only_if` value | Effect |
|-----------------|--------|
| *(absent)* or `null` | Fade all targeted lights — **current behaviour, unchanged** |
| `on` | Only fade lights whose current state is `on` |
| `off` | Only fade lights whose current state is `off` |

The filter is applied **after** light-group expansion and **after** the existing
`unavailable` / capability filtering, so it composes with all existing behaviour.

Lights in any state other than `on`/`off` (e.g. `unknown`) match neither value and
are therefore excluded whenever `only_if` is set. This is intentional and documented.

`only_if` is a *target filter*, not a fade value. On its own (no brightness/colour),
the call still does nothing — it must not be treated as a fade target, so it stays
out of `FadeParams.has_target()` / `has_from_target()`.

## The YAML `on`/`off` boolean gotcha

In YAML, bare `on`/`off`/`yes`/`no`/`true`/`false` parse as **booleans**. An
automation written as `only_if: on` therefore arrives as Python `True`, not the
string `"on"`. The UI's `select` selector sends proper JSON strings, so the form is
unaffected, but YAML automations would break under a naive `vol.In(["on", "off"])`.

The schema validator normalises both forms so users never have to remember to quote
the value:

| Input | Normalised result |
|-------|-------------------|
| *(absent)* or `null` / `None` | `None` → no filter |
| `True` / `"on"` / `"On"` (any case) | `"on"` |
| `False` / `"off"` / `"Off"` (any case) | `"off"` |
| anything else (`"maybe"`, `5`, …) | rejected (`vol.Invalid`) |

Explicit `null` is recognised as "no filter", identical to omitting the key.

## Implementation points

1. **`const.py`** — add `ATTR_ONLY_IF = "only_if"`. Reuse HA's `STATE_ON` / `STATE_OFF`
   constants for the values.

2. **`__init__.py`** — add `vol.Optional(ATTR_ONLY_IF): <normalising validator>` to
   `FADE_LIGHTS_SCHEMA`. The validator implements the normalisation table above,
   passing `None` through unchanged and raising `vol.Invalid` for unrecognised values.

3. **`fade_params.py`** — add `only_if: str | None = None` to `FadeParams`, populated
   in `from_service_data` (`data.get(ATTR_ONLY_IF)`). Kept out of `has_target()` /
   `has_from_target()`. Lives here because `_resolve_fade_targets` already receives a
   `FadeParams`, so no signature churn, and it centralises service-data parsing where
   existing tests already point.

4. **`coordinator.py`** — in `_resolve_fade_targets`, after the `unavailable` check,
   skip any entity where `fade_params.only_if is not None and state.state != fade_params.only_if`,
   logging at debug level.

5. **`services.yaml`** — add an `only_if` field under the collapsed `advanced_fields`
   block, using a `select` selector with `on` / `off` options. No
   `supported_color_modes` filter — it applies to any light regardless of colour
   capability, so it should always be shown.

6. **`strings.json` + `translations/en.json`** — add the field `name` / `description`.
   The other 24 translation files are left for later translation; `check_translations.py`
   treats missing keys as warnings (only stale keys are errors).

7. **`README.md`** — document the parameter in the `fado.fade_lights` usage section,
   with an example automation.

## Testing (TDD — tests written first)

- **Schema** (`tests/test_actions.py` / parameter tests): accepts `"on"`, `"off"`,
  the YAML booleans `True`/`False`, case variants, and `null`; rejects junk strings
  and out-of-range values.
- **`FadeParams.from_service_data`**: parses `only_if` into the dataclass; absent/null
  → `None`; `only_if` does not flip `has_target()`.
- **`_resolve_fade_targets`**: with `only_if="on"`, returns only currently-on lights;
  with `"off"`, only currently-off; unset/null → all (current behaviour). Lights in
  `unknown` state excluded when the filter is set.
- **End-to-end `handle_fade_lights`**: only matching lights are faded (assert via the
  fade tasks / expected-state machinery used by existing integration-style tests).

## Out of scope

- No change to `exclude_lights` / `include_lights`.
- No new filtering dimensions beyond power state (no brightness/colour-range filters).
- No UI changes to the custom card/panel (action is invoked via standard HA forms).
