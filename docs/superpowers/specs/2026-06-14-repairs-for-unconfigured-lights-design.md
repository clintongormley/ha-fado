# Repairs issue for unconfigured lights

## Problem

When Fado detects a light that is missing required configuration, it currently
surfaces a **persistent notification** ("N lights detected without
configuration", with a link to the panel). Persistent notifications are the
wrong HA surface for a standing, actionable "needs attention" item — the issue
registry / Repairs dashboard is the canonical home for this. We are switching
the output surface to a Repairs issue.

## Decision summary

- Use the **issue registry / Repairs** surface, not persistent notifications.
- **`is_fixable=False`** — there is no inline fix flow. Setting the missing
  values (`min_delay_ms`, `min_brightness`, `native_transitions`) requires the
  opt-in autoconfigure test, which can't run inside a repair flow. The issue
  links the user to the Fado panel/dashboard, where they opt in.
- **Single aggregate issue**, not one issue per light. Mirrors today's
  notification; one row that auto-clears when all lights are configured. The
  panel remains the place to see *which* lights.

## Scope

Swap only the **output surface**. Detection logic and all trigger points are
unchanged:

- startup (after `EVENT_HOMEASSISTANT_STARTED`, or immediately if already
  running)
- daily timer (`UNCONFIGURED_CHECK_INTERVAL_HOURS`)
- entity-registry `create` / `remove` / re-enable (`disabled_by` change)

## Detailed design

### `notifications.py`

Keep the file name (deliberately **not** `repairs.py` — HA treats `repairs.py`
as the repairs *platform* and looks for `async_create_fix_flow` there; we have
no fix flow, so we avoid the collision). Keep the public function name
`_notify_unconfigured_lights` so the six callers in `__init__.py` /
`websocket_api.py` are untouched.

Unchanged: `_get_unconfigured_lights()` (detection),
`_get_config_entry()`, and the link-resolution helper
(`_get_notification_link_url()` → `/fado` if sidebar on, else the dashboard URL
option, else `""`).

New body of `_notify_unconfigured_lights()`:

1. Return early if `hass.state is not CoreState.running` (unchanged guard).
2. Resolve the config entry. If `OPTION_NOTIFICATIONS_ENABLED` is off →
   `ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)` and return.
3. `unconfigured = _get_unconfigured_lights(hass)`.
4. If `unconfigured`:
   - `count = len(unconfigured)`
   - `link = _get_notification_link_url(hass)` (or its replacement name)
   - `ir.async_create_issue(`
     `hass, DOMAIN, UNCONFIGURED_ISSUE_ID,`
     `is_fixable=False,`
     `severity=IssueSeverity.WARNING,`
     `translation_key="unconfigured_lights",`
     `translation_placeholders={"count": str(count)},`
     `learn_more_url=link or None,`
     `)`
   - `async_create_issue` is idempotent and keyed by
     `(DOMAIN, UNCONFIGURED_ISSUE_ID)`, so repeated calls from all triggers
     refresh the single row (including the count placeholder).
5. Else → `ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)`.
6. **Upgrade cleanup:** also dismiss the legacy persistent notification once
   (`persistent_notification.async_dismiss(hass, LEGACY_NOTIFICATION_ID)`) so
   upgraders don't keep a stale notification alongside the new issue.

`is_persistent` is left at its default (`False`): the issue is re-evaluated on
every check, so it should not survive a restart on its own.

### `const.py`

- Replace `NOTIFICATION_ID = "fado_unconfigured"` with
  `UNCONFIGURED_ISSUE_ID = "unconfigured_lights"` (matches the translation key).
- Add `LEGACY_NOTIFICATION_ID = "fado_unconfigured"` for the one-time
  upgrade-cleanup dismiss.
- `REQUIRED_CONFIG_FIELDS` and `UNCONFIGURED_CHECK_INTERVAL_HOURS` unchanged.

### `__init__.py`

`async_remove_entry` (full integration removal): replace the
`persistent_notification.async_dismiss(NOTIFICATION_ID)` with
`ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)`, and also dismiss
the legacy notification (`LEGACY_NOTIFICATION_ID`) for upgraders.

### i18n: `strings.json` + all `translations/*.json`

**Every user-facing string for the repair is internationalized** — there is no
hardcoded English in Python (unlike today's notification, whose title and
message are f-strings in `notifications.py`). The Python code passes only a
`translation_key` and a `{count}` placeholder; HA renders the localized
title/description.

`strings.json` is the source of truth. `en.json` mirrors it. There are **25
locale files** in `translations/` (en + 24 others); none currently have an
`issues` section.

Changes, applied to `strings.json` **and** every `translations/<lang>.json`:

- Add an `issues` section:

  ```json
  "issues": {
    "unconfigured_lights": {
      "title": "Lights need configuration",
      "description": "{count} light(s) detected without Fado configuration. Open Fado to set them up."
    }
  }
  ```

  Keep the `{count}` placeholder; exact copy may be polished during
  implementation but the title/description structure above is the contract.
  Placeholder substitution is plain `{count}` only (no ICU plural), so phrase
  for count-independence — title is always plural ("Lights need
  configuration"); description uses "light(s)" or each language's natural
  phrasing. The old Python `light{'s' if count != 1 else ''}` pluralization is
  dropped.

- Reword the two existing option strings that mention persistent notifications
  / notification links to point at the Repairs dashboard (Settings → System →
  Repairs). This is a **content** change to already-present keys — the
  key-based `check_translations.py` will NOT flag it, so the translated
  *values* must be updated in every locale, not just `strings.json`/`en.json`.
  The option **key** `notifications_enabled` is kept (no config-entry migration
  → no reset of existing users' preference); only the human-facing
  label/description change.

**Translations must be complete.** The new `issues` block and the reworded
option strings are translated into **all 25 locales** — this is a hard
acceptance criterion for the change, not best-effort. `check_translations.py`
treats missing keys as warnings only, so a green checker is necessary but **not
sufficient**: completeness is verified by confirming every
`translations/<lang>.json` carries a fully translated `issues.unconfigured_lights`
block (title + description, `{count}` preserved) and updated option-string
values. (Stale keys remain a hard error; this change removes no keys and keeps
`notifications_enabled`, so no stale keys are introduced.)

### Tests (`test_notifications.py`)

- Detection tests for `_get_unconfigured_lights()` are unchanged.
- Output-surface tests move from asserting on `persistent_notification` to the
  **issue registry**: assert the issue is created with the right
  `issue_id` / `translation_key` / `translation_placeholders["count"]` /
  `severity` / `is_fixable=False` / `learn_more_url` when unconfigured lights
  exist; asserted **absent** when all configured, when notifications are
  disabled, and after removal.
- TDD: write the failing issue-registry assertions first, then change the
  implementation.

## Risk / verification

- **Relative `learn_more_url`.** Our link is a relative path (`/fado` or the
  configured dashboard URL), whereas most integrations pass an absolute docs
  URL. Verify the Repairs dialog navigates a relative `learn_more_url`
  correctly. **Fallback** if it doesn't: drop `learn_more_url` and embed a
  markdown link in the translated `description` (the Repairs dialog renders the
  description via `ha-markdown`). This is the single thing to prove out during
  implementation.
- **HA version.** `homeassistant.helpers.issue_registry`
  (`async_create_issue` / `async_delete_issue` / `IssueSeverity`) is well
  within the project's minimum HA (2025.2.0).

## Out of scope

- No fix flow / `repairs.py` platform file.
- No per-light issues.
- No change to detection logic, trigger points, or the
  `notifications_enabled` option key.
