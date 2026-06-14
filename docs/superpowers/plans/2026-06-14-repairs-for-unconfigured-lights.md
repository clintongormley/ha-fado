# Repairs Issue for Unconfigured Lights — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the persistent-notification surface for unconfigured lights with a single aggregate Repairs issue, fully internationalized across all 25 locales.

**Architecture:** Detection logic and all trigger points (startup, daily timer, entity-registry create/remove/re-enable) are unchanged. Only the output surface changes: `_notify_unconfigured_lights()` drives the HA issue registry (`async_create_issue` / `async_delete_issue`) instead of `persistent_notification`. The issue is `is_fixable=False`, severity `WARNING`, keyed `(DOMAIN, "unconfigured_lights")`, with a `{count}` translation placeholder and a `learn_more_url` pointing at the Fado panel/dashboard (or `None` when no link is configured). All user-facing text lives in `strings.json` + `translations/*.json`.

**Tech Stack:** Home Assistant custom integration (Python 3.14), `homeassistant.helpers.issue_registry`, pytest + `pytest_homeassistant_custom_component`, ruff, pyright.

**Spec:** [docs/superpowers/specs/2026-06-14-repairs-for-unconfigured-lights-design.md](../specs/2026-06-14-repairs-for-unconfigured-lights-design.md)

---

## File Structure

| File | Change |
| --- | --- |
| `custom_components/fado/const.py` | Replace `NOTIFICATION_ID` with `UNCONFIGURED_ISSUE_ID` + `LEGACY_NOTIFICATION_ID` |
| `custom_components/fado/notifications.py` | `_notify_unconfigured_lights()` drives the issue registry; drop `persistent_notification` import |
| `custom_components/fado/__init__.py` | Fix const import; `async_remove_entry` deletes the issue; one-time legacy-notification dismiss on setup |
| `custom_components/fado/strings.json` | Add `issues.unconfigured_lights`; reword two option strings |
| `custom_components/fado/translations/en.json` | Mirror `strings.json` |
| `custom_components/fado/translations/<24 locales>.json` | Translated `issues` block + reworded option values |
| `tests/test_notifications.py` | Output-surface tests assert the issue registry; add setup/remove migration tests |

`notifications.py` keeps its filename deliberately — **not** `repairs.py`, which HA treats as the repairs *platform* (it looks for `async_create_fix_flow` there). We have no fix flow, so we avoid that collision. The public function name `_notify_unconfigured_lights` is kept so the six callers in `__init__.py` / `websocket_api.py` are untouched.

---

## API reference (verified against installed HA)

```python
# homeassistant/helpers/issue_registry.py
def async_create_issue(
    hass, domain, issue_id, *,
    breaks_in_ha_version=None, data=None,
    is_fixable,                       # required kw
    is_persistent=False,
    issue_domain=None, learn_more_url=None,
    severity,                         # required kw: IssueSeverity
    translation_key,                  # required kw
    translation_placeholders=None,
) -> None: ...

def async_delete_issue(hass, domain, issue_id) -> None: ...

class IssueSeverity(StrEnum):  # values: "critical", "error", "warning"
    WARNING = "warning"

# reading back in tests:
ir.async_get(hass).async_get_issue(domain, issue_id) -> IssueEntry | None
# IssueEntry fields incl: is_fixable, severity, translation_key,
#   translation_placeholders, learn_more_url
```

---

### Task 1: Swap the live notification surface to the issue registry

**Files:**
- Modify: `custom_components/fado/const.py:130-133`
- Modify: `custom_components/fado/notifications.py` (imports + `_notify_unconfigured_lights`)
- Modify: `custom_components/fado/__init__.py:55-73` (const import) and `:374-381` (`async_remove_entry`)
- Test: `tests/test_notifications.py`

This task changes the constant name, so every importer must move together to keep the package importable. Do all edits, then run the full notifications suite green before committing.

- [ ] **Step 1: Update the constants**

In `custom_components/fado/const.py`, replace:

```python
# Notification for unconfigured lights
NOTIFICATION_ID = "fado_unconfigured"
```

with:

```python
# Repairs issue for unconfigured lights
UNCONFIGURED_ISSUE_ID = "unconfigured_lights"  # also the translation_key
# Pre-Repairs persistent-notification id, dismissed on upgrade for cleanup
LEGACY_NOTIFICATION_ID = "fado_unconfigured"
```

Leave `REQUIRED_CONFIG_FIELDS` and `UNCONFIGURED_CHECK_INTERVAL_HOURS` unchanged.

- [ ] **Step 2: Rewrite the failing tests in `tests/test_notifications.py`**

Update the imports block (top of file):

```python
from homeassistant.helpers import issue_registry as ir

from custom_components.fado.const import (
    DOMAIN,
    LEGACY_NOTIFICATION_ID,
    OPTION_DASHBOARD_URL,
    OPTION_NOTIFICATIONS_ENABLED,
    OPTION_SHOW_SIDEBAR,
    UNCONFIGURED_ISSUE_ID,
)
```

Replace the entire `class TestNotifyUnconfiguredLights` with:

```python
class TestNotifyUnconfiguredLights:
    """_notify_unconfigured_lights drives the issue registry."""

    async def test_creates_issue_when_unconfigured(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_create_issue") as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert args[0] is hass
        assert args[1] == DOMAIN
        assert args[2] == UNCONFIGURED_ISSUE_ID
        assert kwargs["is_fixable"] is False
        assert kwargs["severity"] == ir.IssueSeverity.WARNING
        assert kwargs["translation_key"] == UNCONFIGURED_ISSUE_ID
        assert kwargs["translation_placeholders"] == {"count": "1"}
        assert kwargs["learn_more_url"] == "/fado"

    async def test_issue_count_placeholder_plural(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        mock_entries = []
        for name in ["bedroom", "kitchen"]:
            entry = MagicMock()
            entry.entity_id = f"light.{name}"
            entry.domain = LIGHT_DOMAIN
            entry.disabled = False
            mock_entries.append(entry)

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_create_issue") as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = mock_entries
            await _notify_unconfigured_lights(hass)

        _, kwargs = mock_create.call_args
        assert kwargs["translation_placeholders"] == {"count": "2"}

    async def test_deletes_issue_when_all_configured(self, hass: HomeAssistant) -> None:
        _make_coordinator(
            hass,
            {
                "light.bedroom": {
                    "min_delay_ms": 100,
                    "min_brightness": 1,
                    "native_transitions": True,
                }
            },
        )
        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_delete_issue") as mock_delete,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_delete.assert_called_once_with(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)

    async def test_deletes_issue_when_no_lights(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_delete_issue") as mock_delete,
        ):
            mock_er.return_value.entities.values.return_value = []
            await _notify_unconfigured_lights(hass)

        mock_delete.assert_called_once_with(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)
```

Replace `class TestNotifySkippedBeforeStart` so both tests assert against the issue registry:

```python
class TestNotifySkippedBeforeStart:
    """Issue is not touched before HA has fully started."""

    async def test_skips_when_ha_not_running(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        hass.state = CoreState.starting

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_create_issue") as mock_create,
            patch("custom_components.fado.notifications.ir.async_delete_issue") as mock_delete,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_create.assert_not_called()
        mock_delete.assert_not_called()

    async def test_entity_registry_create_during_startup_no_issue(
        self, hass: HomeAssistant
    ) -> None:
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

        hass.state = CoreState.starting

        with patch(
            "custom_components.fado.notifications.ir.async_create_issue"
        ) as mock_create:
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {"action": "create", "entity_id": "light.new_group"},
            )
            await hass.async_block_till_done()

        mock_create.assert_not_called()
```

In `class TestNotificationsDisabled`, replace the three tests so they assert the issue registry:

```python
    async def test_disabled_deletes_issue(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={OPTION_NOTIFICATIONS_ENABLED: False},
        )
        entry.add_to_hass(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_create_issue") as mock_create,
            patch("custom_components.fado.notifications.ir.async_delete_issue") as mock_delete,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_create.assert_not_called()
        mock_delete.assert_called_once_with(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)

    async def test_sidebar_disabled_uses_dashboard_url(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                OPTION_SHOW_SIDEBAR: False,
                OPTION_DASHBOARD_URL: "/lovelace-fado/0",
                OPTION_NOTIFICATIONS_ENABLED: True,
            },
        )
        entry.add_to_hass(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_create_issue") as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        _, kwargs = mock_create.call_args
        assert kwargs["learn_more_url"] == "/lovelace-fado/0"

    async def test_sidebar_disabled_no_url_no_link(self, hass: HomeAssistant) -> None:
        _make_coordinator(hass)
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                OPTION_SHOW_SIDEBAR: False,
                OPTION_NOTIFICATIONS_ENABLED: True,
            },
        )
        entry.add_to_hass(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch("custom_components.fado.notifications.ir.async_create_issue") as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        _, kwargs = mock_create.call_args
        assert kwargs["learn_more_url"] is None
```

Note: `TestNotificationLinkUrl` (tests `_get_notification_link_url`) and the
detection tests (`TestGetUnconfiguredLights`) are unchanged — the helper names
and detection behavior are preserved.

- [ ] **Step 3: Run the rewritten tests to verify they fail**

Run: `python -m pytest tests/test_notifications.py -q`
Expected: FAIL — `ImportError` for `UNCONFIGURED_ISSUE_ID` from notifications.py / `notifications.ir` does not exist yet.

- [ ] **Step 4: Rewrite `custom_components/fado/notifications.py`**

Replace the imports (lines 5-21) — drop `persistent_notification`, add `issue_registry`, swap the const name:

```python
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import (
    DEFAULT_DASHBOARD_URL,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_SHOW_SIDEBAR,
    DOMAIN,
    OPTION_DASHBOARD_URL,
    OPTION_NOTIFICATIONS_ENABLED,
    OPTION_SHOW_SIDEBAR,
    REQUIRED_CONFIG_FIELDS,
    UNCONFIGURED_ISSUE_ID,
)
from .coordinator import FadeCoordinator
```

Replace the body of `_notify_unconfigured_lights` (keep the docstring intent, update wording):

```python
async def _notify_unconfigured_lights(hass: HomeAssistant) -> None:
    """Check for unconfigured lights and create/clear the Repairs issue.

    If there are unconfigured lights, creates (or refreshes) a single aggregate
    issue in the issue registry with a count and a learn-more link to the Fado
    panel/dashboard. If all lights are configured — or notifications are
    disabled — deletes any existing issue.

    Skipped before HA has fully started because entity states (needed to detect
    light groups) are not yet available.
    """
    if hass.state is not CoreState.running:
        return

    entry = _get_config_entry(hass)
    if entry:
        notifications_enabled = entry.options.get(
            OPTION_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED
        )
        if not notifications_enabled:
            ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)
            return

    unconfigured = _get_unconfigured_lights(hass)

    if unconfigured:
        link_url = _get_notification_link_url(hass)
        ir.async_create_issue(
            hass,
            DOMAIN,
            UNCONFIGURED_ISSUE_ID,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=UNCONFIGURED_ISSUE_ID,
            translation_placeholders={"count": str(len(unconfigured))},
            learn_more_url=link_url or None,
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)
```

- [ ] **Step 5: Fix `custom_components/fado/__init__.py`**

In the `.const` import block (around line 55-70), remove `NOTIFICATION_ID,` and add (alphabetical-ish, matching existing order) `LEGACY_NOTIFICATION_ID,` and `UNCONFIGURED_ISSUE_ID,`.

Add an issue-registry import alongside the other `homeassistant.helpers` imports near the top of the file:

```python
from homeassistant.helpers import issue_registry as ir
```

Rewrite `async_remove_entry` (lines 374-381):

```python
async def async_remove_entry(hass: HomeAssistant, _entry: ConfigEntry) -> None:
    """Remove a config entry — delete stored data and clear the Repairs issue."""
    store: Store[dict[str, int]] = Store(hass, 1, STORAGE_KEY)
    await store.async_remove()

    ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)

    # Clean up the pre-Repairs persistent notification for upgraders that remove
    # the entry without restarting HA.
    from homeassistant.components import persistent_notification  # noqa: PLC0415

    persistent_notification.async_dismiss(hass, LEGACY_NOTIFICATION_ID)
```

- [ ] **Step 6: Run the notifications suite to verify it passes**

Run: `python -m pytest tests/test_notifications.py -q`
Expected: PASS (all tests, including the unchanged detection / link-url tests).

- [ ] **Step 7: Run the full suite to confirm nothing else broke**

Run: `python -m pytest -q`
Expected: PASS. (No other module imports `NOTIFICATION_ID`; `websocket_api.py` only imports the function, which is unchanged.)

- [ ] **Step 8: Commit**

```bash
git add custom_components/fado/const.py custom_components/fado/notifications.py \
        custom_components/fado/__init__.py tests/test_notifications.py
git commit -m "feat: surface unconfigured lights via a Repairs issue instead of a notification"
```

---

### Task 2: One-time legacy-notification dismiss on setup + remove-entry test

**Files:**
- Modify: `custom_components/fado/__init__.py` (`async_setup_entry`)
- Test: `tests/test_notifications.py`

Handles the upgrade path where a user reloads the integration without restarting
HA: the old in-memory persistent notification would otherwise linger alongside
the new issue. `async_dismiss` early-returns when the id is absent, so this is a
safe no-op once the notification is gone (and in tests).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_notifications.py`:

```python
class TestUpgradeCleanup:
    """Legacy persistent notification is cleaned up; issue cleared on removal."""

    async def test_setup_dismisses_legacy_notification(self, hass: HomeAssistant) -> None:
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights"),
            patch("custom_components.fado._apply_stored_log_level"),
            patch(
                "homeassistant.components.persistent_notification.async_dismiss"
            ) as mock_dismiss,
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

        mock_dismiss.assert_any_call(hass, LEGACY_NOTIFICATION_ID)

    async def test_remove_entry_deletes_issue(self, hass: HomeAssistant) -> None:
        from custom_components.fado import async_remove_entry

        ir.async_create_issue(
            hass,
            DOMAIN,
            UNCONFIGURED_ISSUE_ID,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=UNCONFIGURED_ISSUE_ID,
        )
        assert ir.async_get(hass).async_get_issue(DOMAIN, UNCONFIGURED_ISSUE_ID) is not None

        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        await async_remove_entry(hass, entry)

        assert ir.async_get(hass).async_get_issue(DOMAIN, UNCONFIGURED_ISSUE_ID) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_notifications.py::TestUpgradeCleanup -q`
Expected: FAIL — `test_setup_dismisses_legacy_notification` fails (setup does not dismiss yet). `test_remove_entry_deletes_issue` should already PASS from Task 1; that's fine.

- [ ] **Step 3: Add the one-time dismiss to `async_setup_entry`**

In `custom_components/fado/__init__.py`, inside `async_setup_entry`, near the top (after the entry is in `hass.data` / before the unconfigured-check wiring), add:

```python
    # One-time cleanup: drop the pre-Repairs persistent notification so an
    # in-place reload after upgrade doesn't show it alongside the new issue.
    from homeassistant.components import persistent_notification  # noqa: PLC0415

    persistent_notification.async_dismiss(hass, LEGACY_NOTIFICATION_ID)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_notifications.py::TestUpgradeCleanup -q`
Expected: PASS (both tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/fado/__init__.py tests/test_notifications.py
git commit -m "feat: dismiss legacy unconfigured-lights notification on upgrade"
```

---

### Task 3: Source strings (`strings.json` + `en.json`)

**Files:**
- Modify: `custom_components/fado/strings.json`
- Modify: `custom_components/fado/translations/en.json`

No code test; validated by `check_translations.py` and `pytest` (HA loads strings during entry setup). `en.json` must mirror `strings.json` exactly.

- [ ] **Step 1: Add the `issues` block to `strings.json`**

Add a top-level `"issues"` key (sibling to `"options"`, `"config"`, `"services"`):

```json
  "issues": {
    "unconfigured_lights": {
      "title": "Lights need configuration",
      "description": "{count} light(s) detected without Fado configuration. Open Fado to configure them so fading works smoothly."
    }
  },
```

- [ ] **Step 2: Reword the two option strings in `strings.json`**

Under `options.step.init`:

`data.notifications_enabled`: change `"Enable notifications"` → `"Notify about unconfigured lights"`.

`data_description.notifications_enabled`: change to
`"Create a repair under Settings → System → Repairs when lights are detected without Fado configuration."`

`data_description.dashboard_url`: change the second sentence so it reads
`"URL path for your custom Fado dashboard (e.g. /lovelace-fado/0). Used as the repair's link when the sidebar panel is disabled. Leave blank to omit the link."`

- [ ] **Step 3: Mirror the same three string values + `issues` block into `en.json`**

Apply the identical `issues` block and the same three reworded values to
`custom_components/fado/translations/en.json` (same JSON structure).

- [ ] **Step 4: Validate**

Run: `python scripts/check_translations.py`
Expected: `no stale keys ✓` (en.json now matches strings.json; other locales report the new `issues.*` keys as *untranslated warnings* only — handled in Task 4).

Run: `python -m pytest tests/test_config_flow.py -q`
Expected: PASS (options flow still loads its strings).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/strings.json custom_components/fado/translations/en.json
git commit -m "i18n: add Repairs issue strings and reword notification options (source + en)"
```

---

### Task 4: Translate into the remaining 24 locales (completeness is mandatory)

**Files (modify all 24):**
`custom_components/fado/translations/` — `bg, cs, da, de, es, fi, fr, hu, id, it, ja, ko, nb, nl, pl, pt, ro, sk, sl, sv, tr, uk, vi, zh-Hans`.json

Translation completeness across all locales is a hard acceptance criterion (per
spec). `check_translations.py` only *warns* on missing keys, so a green checker
is necessary but **not sufficient** — every locale must carry a fully translated
`issues.unconfigured_lights` block and updated option-string values.

English source of truth (the contract — translate faithfully, preserving the
`{count}` placeholder and HA's standard term for "Repairs"):

```
issues.unconfigured_lights.title       = "Lights need configuration"
issues.unconfigured_lights.description = "{count} light(s) detected without Fado configuration. Open Fado to configure them so fading works smoothly."
options…data.notifications_enabled               = "Notify about unconfigured lights"
options…data_description.notifications_enabled   = "Create a repair under Settings → System → Repairs when lights are detected without Fado configuration."
options…data_description.dashboard_url           = "URL path for your custom Fado dashboard (e.g. /lovelace-fado/0). Used as the repair's link when the sidebar panel is disabled. Leave blank to omit the link."
```

This is per-locale content generation, not a mechanical copy. It parallelizes
cleanly (one locale per worker). For each locale, match the tone/terminology of
the strings already in that file.

- [ ] **Step 1: For each of the 24 locales, add a translated `issues` block**

Insert the `"issues"` key (same JSON shape as Task 3) with `title` and
`description` translated into the target language; keep `{count}` literal.

- [ ] **Step 2: For each of the 24 locales, update the three reworded option values**

Replace the existing translated values for `notifications_enabled` (label),
`notifications_enabled` (description), and `dashboard_url` (description) with
translations of the new English source above. The **keys** already exist in
each file — only the values change.

- [ ] **Step 3: Validate JSON + key hygiene**

Run: `python -c "import json,glob; [json.load(open(f)) for f in glob.glob('custom_components/fado/translations/*.json')]; print('all JSON valid')"`
Expected: `all JSON valid`

Run: `python scripts/check_translations.py`
Expected: `no stale keys ✓` (no stale-key errors; with Task 4 done there should be no untranslated-key warnings for `issues.*` either).

- [ ] **Step 4: Verify completeness explicitly (checker warnings are not sufficient)**

Run:
```bash
python - <<'PY'
import glob, json
miss = []
for f in sorted(glob.glob("custom_components/fado/translations/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    node = d.get("issues", {}).get("unconfigured_lights", {})
    if not node.get("title") or not node.get("description"):
        miss.append(f)
print("INCOMPLETE:", miss if miss else "none — all 25 locales have the issues block")
PY
```
Expected: `none — all 25 locales have the issues block`

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/translations/
git commit -m "i18n: translate Repairs issue strings and reworded options into all locales"
```

---

### Task 5: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Lint + format**

Run: `ruff check . && ruff format --check .`
Expected: no errors. (If `ruff format --check` reports changes, run `ruff format .` and amend the relevant commit.)

- [ ] **Step 2: Type check**

Run: `npx pyright custom_components/fado/notifications.py custom_components/fado/__init__.py`
Expected: 0 errors. (Common gotcha: `learn_more_url=link_url or None` — `link_url` is `str`, so the expression is `str | None`, which matches the param type.)

- [ ] **Step 3: Full test suite**

Run: `python -m pytest -q`
Expected: PASS, no failures.

- [ ] **Step 4: hassfest schema check for issue translations (if available)**

Run: `python -m script.hassfest --integration-path custom_components/fado` (only if the HA `script.hassfest` is importable in this environment; otherwise note it runs in CI). Expected: passes — the `issues` block matches HA's required `title` + `description` schema.

- [ ] **Step 5: Confirm no `NOTIFICATION_ID` / stray `persistent_notification.async_create` remain**

Run: `grep -rn "NOTIFICATION_ID\|persistent_notification.async_create" custom_components/`
Expected: only `LEGACY_NOTIFICATION_ID` (const definition + the two dismiss call sites). No `async_create` of a persistent notification anywhere.

---

## Self-Review

**Spec coverage:**
- Issue registry surface, `is_fixable=False`, WARNING, single aggregate, `{count}` placeholder, `learn_more_url` → Task 1. ✓
- All trigger points unchanged (function name preserved, callers untouched) → Task 1. ✓
- `async_remove_entry` deletes the issue → Task 1; tested in Task 2. ✓
- Upgrade cleanup of legacy notification → Task 1 (remove) + Task 2 (setup). ✓
- `notifications_enabled` key kept, label/description reworded → Tasks 3-4. ✓
- Full i18n, no hardcoded English in Python → Task 1 (only key + placeholder) + Tasks 3-4. ✓
- Translation completeness across all 25 locales → Task 3 (source+en) + Task 4 (24) + explicit completeness check (Task 4 Step 4). ✓
- `learn_more_url` relative-path risk → carried as the verification note below (manual check during review).

**`learn_more_url` relative-path verification (from spec):** the link is a
relative path (`/fado` or the dashboard URL). Confirm the Repairs dialog
navigates a relative `learn_more_url` when the issue is clicked in a running HA.
If it does not, the fallback is to drop `learn_more_url` and embed a markdown
link in the translated `description` (the Repairs dialog renders the description
via `ha-markdown`); that would shift the link text into the i18n strings. This
is a behavioral check best done against a live HA instance during review, not a
unit test.

**Placeholder scan:** no TBD/TODO; all code blocks complete. Translation task
defines the English contract and per-locale generation (legitimate content
work, not a code placeholder). ✓

**Type/name consistency:** `UNCONFIGURED_ISSUE_ID` and `LEGACY_NOTIFICATION_ID`
used identically across const/notifications/__init__/tests; `_notify_unconfigured_lights`
and `_get_notification_link_url` names preserved; `ir.async_create_issue` /
`ir.async_delete_issue` / `ir.IssueSeverity.WARNING` match the verified HA API. ✓
