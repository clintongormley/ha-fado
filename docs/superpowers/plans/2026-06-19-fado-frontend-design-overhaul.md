# Fado Frontend Design Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the build-less vanilla-JS Fado frontend a `--fado-*` token layer, `ha-select`-based controls, modern HA font vars, and a responsive collapsible-card view for narrow widths — behaviour-preserving, with pure logic extracted and unit-tested.

**Architecture:** Pure logic moves into a new lit-free `fado-logic.js` module (vitest-testable). The shared `FadoCoreMixin` gains a token `css` block, an `ha-select` migration, and a `_compact` (element-width) flag that switches between the existing table render and a new collapsible-card render. The card view groups lights under area headers, flags lights that "need setup", and rolls the count up to the area header.

**Tech Stack:** Vanilla JS + `lit-element@2.4.0` (from unpkg CDN, runtime); vitest + happy-dom for unit tests (dev-only, root `package.json`); HA `ha-*` web components; HA CSS theme variables.

## Global Constraints

- **Behaviour-preserving:** no change to WebSocket message types, custom-event names, handler signatures, entity keys, or engine logic. Markup + styling + pure-logic extraction (identical outputs) only.
- **Registered-or-fallback for `ha-*`:** any new HA element (`ha-select`) is guarded with `customElements.get(name)` and falls back to the existing native control for old HA, mirroring the current `ha-input`/`ha-textfield` pattern at `fado-common.js:840-871`.
- **`e.stopPropagation()`** on every re-emitted composed event (`value-changed`, `change`) crossing a shadow boundary.
- **No raw `title=`** tooltips; use visible mini-labels.
- **Theme via HA CSS custom properties;** never hardcode chrome hex/spacing — every `--fado-*` colour token pairs with the real HA var as fallback.
- **Element-width breakpoint = 720px** everywhere (JS `_compact` flag and CSS rules use the same value).
- **localStorage key** stays `fado_collapsed`; `STORAGE_VERSION` bumps `2 → 3`.
- **Files shipped by HACS live under `custom_components/fado/`.** Test toolchain (`package.json`, `node_modules`, `vitest.config.js`, `tests/frontend/`) lives at the repo root, outside that directory.
- **Changelog:** every user-facing change recorded in `CHANGES.md` under `## [Unreleased]` (Keep a Changelog categories).
- Run `ruff check .`, `ruff format .`, `npx pyright` clean before any PR (no Python change expected, but the repo requires it).

---

## File Structure

- Create `package.json` (root) — vitest/happy-dom dev toolchain + `test` script.
- Create `vitest.config.js` (root) — happy-dom env, `tests/frontend/**` include.
- Create `custom_components/fado/frontend/fado-logic.js` — pure, lit-free logic.
- Create `tests/frontend/fado-logic.test.js` — unit tests for the above.
- Modify `custom_components/fado/frontend/fado-common.js` — import + delegate to fado-logic; `fadoTokens`; font vars; `ha-select`; `_compact` + card view.
- Create `docs/developers/design-system.md` — tokens, conventions, breakpoint, indicator.
- Modify `CLAUDE.md` — "Frontend design system" pointer.
- Modify `CHANGES.md` — Unreleased entries.
- Modify `.gitignore` — add `node_modules/`.

---

# PHASE 1 — Foundation (PR 1)

### Task 1: Test toolchain

**Files:**
- Create: `package.json`
- Create: `vitest.config.js`
- Modify: `.gitignore`
- Test: `tests/frontend/smoke.test.js` (temporary, deleted in Step 6)

**Interfaces:**
- Produces: an `npm test` script that runs vitest against `tests/frontend/**/*.test.js` in a happy-dom environment.

- [ ] **Step 1: Add `node_modules/` to `.gitignore`**

Append to `.gitignore`:

```
# Node test toolchain
node_modules/
```

- [ ] **Step 2: Create `package.json`**

```json
{
  "name": "ha-fado-frontend-tests",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 3: Install dev dependencies**

Run: `npm install -D vitest happy-dom`
Expected: `node_modules/` created; `devDependencies` added to `package.json`; `package-lock.json` written.

- [ ] **Step 4: Create `vitest.config.js`**

```js
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "happy-dom",
    include: ["tests/frontend/**/*.test.js"],
  },
});
```

- [ ] **Step 5: Add a smoke test and run it**

Create `tests/frontend/smoke.test.js`:

```js
import { describe, it, expect } from "vitest";

describe("toolchain", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run: `npm test`
Expected: PASS (1 test).

- [ ] **Step 6: Remove smoke test, commit**

```bash
rm tests/frontend/smoke.test.js
git add package.json package-lock.json vitest.config.js .gitignore
git commit -m "test: add vitest + happy-dom frontend test toolchain"
```

---

### Task 2: Pure logic module `fado-logic.js`

**Files:**
- Create: `custom_components/fado/frontend/fado-logic.js`
- Test: `tests/frontend/fado-logic.test.js`

**Interfaces:**
- Produces (all named exports):
  - `needsSetup(light) -> boolean`
  - `areaNeedsSetupCount(area) -> number`
  - `needsSetupLabel(count) -> string`
  - `getCheckboxState(entityIds: string[], configureChecked: Set<string>) -> "none"|"some"|"all"`
  - `getExcludeState(lights) -> "none"|"some"|"all"`
  - `collapseKeyForArea(area) -> string`
  - `collapseKeyForLight(entityId: string) -> string`
  - `nativeTransitionsToValue(nt) -> "" | "true" | "false" | "disable"`
  - `valueToNativeTransitions(value) -> null | true | false | "disable"`

- [ ] **Step 1: Write the failing tests**

Create `tests/frontend/fado-logic.test.js`:

```js
import { describe, it, expect } from "vitest";
import {
  needsSetup,
  areaNeedsSetupCount,
  needsSetupLabel,
  getCheckboxState,
  getExcludeState,
  collapseKeyForArea,
  collapseKeyForLight,
  nativeTransitionsToValue,
  valueToNativeTransitions,
} from "../../custom_components/fado/frontend/fado-logic.js";

describe("needsSetup", () => {
  it("true when no min delay and not excluded", () => {
    expect(needsSetup({ min_delay_ms: null, exclude: false })).toBe(true);
    expect(needsSetup({ exclude: false })).toBe(true);
  });
  it("false when a min delay is set", () => {
    expect(needsSetup({ min_delay_ms: 100, exclude: false })).toBe(false);
  });
  it("false when excluded", () => {
    expect(needsSetup({ min_delay_ms: null, exclude: true })).toBe(false);
  });
});

describe("areaNeedsSetupCount / needsSetupLabel", () => {
  const area = {
    lights: [
      { min_delay_ms: null, exclude: false },
      { min_delay_ms: 100, exclude: false },
      { min_delay_ms: null, exclude: true },
      { min_delay_ms: null, exclude: false },
    ],
  };
  it("counts only lights needing setup", () => {
    expect(areaNeedsSetupCount(area)).toBe(2);
  });
  it("labels with pluralisation", () => {
    expect(needsSetupLabel(0)).toBe("");
    expect(needsSetupLabel(1)).toBe("1 needs setup");
    expect(needsSetupLabel(3)).toBe("3 need setup");
  });
});

describe("getCheckboxState", () => {
  const checked = new Set(["a", "b"]);
  it("none for empty", () => {
    expect(getCheckboxState([], checked)).toBe("none");
  });
  it("all when every id checked", () => {
    expect(getCheckboxState(["a", "b"], checked)).toBe("all");
  });
  it("none when no id checked", () => {
    expect(getCheckboxState(["x", "y"], checked)).toBe("none");
  });
  it("some when partially checked", () => {
    expect(getCheckboxState(["a", "x"], checked)).toBe("some");
  });
});

describe("getExcludeState", () => {
  it("none for empty", () => {
    expect(getExcludeState([])).toBe("none");
  });
  it("all / none / some", () => {
    expect(getExcludeState([{ exclude: true }, { exclude: true }])).toBe("all");
    expect(getExcludeState([{ exclude: false }, { exclude: false }])).toBe("none");
    expect(getExcludeState([{ exclude: true }, { exclude: false }])).toBe("some");
  });
});

describe("collapse keys", () => {
  it("area key with id and fallback", () => {
    expect(collapseKeyForArea({ area_id: "kitchen" })).toBe("area_kitchen");
    expect(collapseKeyForArea({ area_id: null })).toBe("area_none");
  });
  it("light key", () => {
    expect(collapseKeyForLight("light.lamp")).toBe("light_light.lamp");
  });
});

describe("native transitions mapping round-trip", () => {
  it("config value -> select value", () => {
    expect(nativeTransitionsToValue(true)).toBe("true");
    expect(nativeTransitionsToValue(false)).toBe("false");
    expect(nativeTransitionsToValue("disable")).toBe("disable");
    expect(nativeTransitionsToValue(null)).toBe("");
    expect(nativeTransitionsToValue(undefined)).toBe("");
  });
  it("select value -> config value", () => {
    expect(valueToNativeTransitions("true")).toBe(true);
    expect(valueToNativeTransitions("false")).toBe(false);
    expect(valueToNativeTransitions("disable")).toBe("disable");
    expect(valueToNativeTransitions("")).toBe(null);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `fado-logic.js` (module not found).

- [ ] **Step 3: Create `fado-logic.js`**

```js
/**
 * Pure, framework-free logic for the Fado frontend.
 *
 * No lit / DOM imports, so this module can be unit-tested with vitest.
 * Consumed by the FadoCoreMixin in fado-common.js — keep these the single
 * source of truth for the predicates and string mappings they cover.
 */

/** A light needs autoconfigure when it has no min delay and isn't excluded. */
export function needsSetup(light) {
  return !light.min_delay_ms && !light.exclude;
}

/** Number of lights in an area that need setup. */
export function areaNeedsSetupCount(area) {
  return area.lights.filter(needsSetup).length;
}

/** Roll-up label for an area header; "" when none need setup. */
export function needsSetupLabel(count) {
  if (!count) return "";
  if (count === 1) return "1 needs setup";
  return `${count} need setup`;
}

/** Tri-state of the configure checkboxes for a set of entity ids. */
export function getCheckboxState(entityIds, configureChecked) {
  if (entityIds.length === 0) return "none";
  const checked = entityIds.filter((id) => configureChecked.has(id)).length;
  if (checked === 0) return "none";
  if (checked === entityIds.length) return "all";
  return "some";
}

/** Tri-state of the exclude flags for a list of lights. */
export function getExcludeState(lights) {
  if (lights.length === 0) return "none";
  const excluded = lights.filter((light) => light.exclude).length;
  if (excluded === 0) return "none";
  if (excluded === lights.length) return "all";
  return "some";
}

/** localStorage collapse key for an area. */
export function collapseKeyForArea(area) {
  return `area_${area.area_id || "none"}`;
}

/** localStorage collapse key for a light card. */
export function collapseKeyForLight(entityId) {
  return `light_${entityId}`;
}

/** native_transitions config value -> <ha-select>/<select> string value. */
export function nativeTransitionsToValue(nt) {
  if (nt === true) return "true";
  if (nt === false) return "false";
  if (nt === "disable") return "disable";
  return "";
}

/** <ha-select>/<select> string value -> native_transitions config value. */
export function valueToNativeTransitions(value) {
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "disable") return "disable";
  return null;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS (all describe blocks green).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/fado-logic.js tests/frontend/fado-logic.test.js
git commit -m "feat(frontend): add pure fado-logic module with unit tests"
```

---

### Task 3: Delegate mixin methods to `fado-logic.js`

Behaviour-preserving refactor: the mixin imports the pure functions and delegates, removing the duplicated inline logic. No unit test for the mixin itself (it imports lit from a CDN URL that vitest can't resolve); the gate is that Task 2's tests still pass and the deploy renders identically.

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

**Interfaces:**
- Consumes: all exports from Task 2.

- [ ] **Step 1: Add the import** at the top of `fado-common.js`, after the lit import block (around line 13):

```js
import {
  needsSetup,
  areaNeedsSetupCount,
  needsSetupLabel,
  getCheckboxState,
  getExcludeState,
  collapseKeyForArea,
  collapseKeyForLight,
  nativeTransitionsToValue,
  valueToNativeTransitions,
} from "./fado-logic.js";
```

- [ ] **Step 2: Delegate the tri-state helpers**

Replace `_getCheckboxState(entityIds)` body (currently `fado-common.js:477-485`) with:

```js
    _getCheckboxState(entityIds) {
      return getCheckboxState(entityIds, this._configureChecked);
    }
```

Replace `_getExcludeState(lights)` body (currently `fado-common.js:514-520`) with:

```js
    _getExcludeState(lights) {
      return getExcludeState(lights);
    }
```

- [ ] **Step 3: Delegate the area collapse key**

In `_initCollapsedState` replace `const areaKey = \`area_${area.area_id || "none"}\`;` (~line 256) with `const areaKey = collapseKeyForArea(area);`.

In `_renderAreaRows` replace `const areaKey = \`area_${area.area_id || "none"}\`;` (~line 797) with `const areaKey = collapseKeyForArea(area);`.

- [ ] **Step 4: Delegate needs-setup in `_initConfigureChecked`**

Replace the inner condition in `_initConfigureChecked` (currently `if (!light.min_delay_ms && !light.exclude)` at ~line 270) with:

```js
            if (needsSetup(light)) {
```

And in `_mergeData` replace `if (!existingLightIds.has(light.entity_id) && !light.min_delay_ms && !light.exclude)` (~line 311) with:

```js
          if (!existingLightIds.has(light.entity_id) && needsSetup(light)) {
```

- [ ] **Step 5: Verify logic tests still pass and lint is clean**

Run: `npm test`
Expected: PASS (unchanged — confirms the extracted functions are stable).

Run: `npx pyright`
Expected: no new errors.

- [ ] **Step 6: Deploy and smoke-check (visual gate)**

Deploy the component (devcontainer): `cp to ha`, then load the Fado panel. Confirm: areas collapse/expand and persist, area/all configure + exclude tri-state checkboxes behave exactly as before, Autoconfigure auto-ticks unconfigured lights. No visible change expected.

- [ ] **Step 7: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js
git commit -m "refactor(frontend): delegate mixin logic to fado-logic module"
```

---

### Task 4: Token layer `fadoTokens` + font-var modernisation

CSS only — no unit test. Gate: visual parity in light + dark + a custom theme.

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

**Interfaces:**
- Produces: an exported `fadoTokens` `css` block applied at `:host`; `static get styles()` returns `[fadoTokens, fadoStyles]`.

- [ ] **Step 1: Define `fadoTokens`** — add immediately before `export const fadoStyles = css\`...\`` (~line 943):

```js
export const fadoTokens = css`
  :host {
    /* Colour — mapped to HA theme vars with real fallbacks */
    --fado-accent: var(--primary-color, #03a9f4);
    --fado-warning: var(--warning-color, #e09112);
    --fado-error: var(--error-color, #db4437);
    --fado-on: var(--amber-color, #ffc107);
    --fado-text: var(--primary-text-color);
    --fado-text-muted: var(--secondary-text-color);
    --fado-border: var(--divider-color);
    --fado-surface: var(--card-background-color);
    --fado-surface-2: var(--secondary-background-color, rgba(0, 0, 0, 0.05));

    /* Structural — fixed but overridable */
    --fado-space-1: 4px;
    --fado-space-2: 8px;
    --fado-space-3: 12px;
    --fado-space-4: 16px;
    --fado-space-5: 24px;
    --fado-space-6: 32px;
    --fado-radius: 8px;
    --fado-radius-sm: 4px;
    --fado-font-sm: var(--ha-font-size-s, var(--paper-font-caption_-_font-size, 12px));
    --fado-font-md: var(--ha-font-size-m, var(--paper-font-body1_-_font-size, 14px));
    --fado-font-lg: 20px;
    --fado-font-h1: var(--ha-card-header-font-size, 24px);
    --fado-font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, sans-serif));
    --fado-control-height: 40px;
  }
`;
```

- [ ] **Step 2: Return the token block from `styles()`** — change `static get styles() { return fadoStyles; }` (~line 41) to:

```js
    static get styles() {
      return [fadoTokens, fadoStyles];
    }
```

- [ ] **Step 3: Reference tokens in `fadoStyles`** — replace the legacy/literal values with tokens. Apply these substitutions throughout `fadoStyles`:
  - `var(--paper-font-body1_-_font-size, 14px)` → `var(--fado-font-md)`
  - `var(--paper-font-caption_-_font-size, 12px)` → `var(--fado-font-sm)`
  - `var(--paper-font-body1_-_font-family, Roboto, sans-serif)` → `var(--fado-font-family)`
  - `var(--ha-card-header-font-size, 24px)` (h1) → `var(--fado-font-h1)`
  - `--primary-text-color` (as a colour value) → `var(--fado-text)`; `--secondary-text-color` → `var(--fado-text-muted)`; `--divider-color` → `var(--fado-border)`
  - `var(--amber-color, #ffc107)` (`.light-icon.on`) → `var(--fado-on)`
  - `var(--error-color, #db4437)` (`.test-error`) → `var(--fado-error)`
  - `var(--secondary-background-color, rgba(0,0,0,0.05))` (`.area-row td`) → `var(--fado-surface-2)`
  - In `.button-spinner`, replace `rgba(255,255,255,0.3)` and `white` with `rgba(255, 255, 255, 0.3)` kept (spinner sits on the accent button so a fixed light ring is correct) — leave as-is but add a comment `/* on-accent spinner: fixed light ring is intentional */`.

  Leave raw `px` paddings/margins as-is for now except where you naturally touch a rule; full spacing tokenisation is not required for parity.

- [ ] **Step 4: Deploy and verify (visual gate)**

`cp to ha`, reload. In **light, dark, and one custom theme** confirm: identical look to before; the light-on icon, error text, area header background, and h1 all render correctly; nothing shrank or recoloured.

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js
git commit -m "feat(frontend): add --fado-* token layer and modern HA font vars"
```

---

### Task 5: Migrate raw `<select>` to `ha-select`

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

**Interfaces:**
- Consumes: `nativeTransitionsToValue`, `valueToNativeTransitions` (Task 2).
- Produces: a `_renderSelect({ value, options, disabled, onChange })` helper used by both selects.

- [ ] **Step 1: Add a guarded select helper** — add near `_renderNumberInput` (~line 840):

```js
    _renderSelect({ value, options, disabled, onChange }) {
      // ha-select is the modern HA control; fall back to a native <select>
      // on much-older HA that hasn't registered it yet.
      if (customElements.get("ha-select")) {
        return html`
          <ha-select
            naturalMenuWidth
            ?disabled=${disabled}
            .value=${value}
            @selected=${(e) => { e.stopPropagation(); onChange(e.target.value); }}
            @closed=${(e) => e.stopPropagation()}
          >
            ${options.map(
              (o) => html`<ha-list-item .value=${o.value}>${o.label}</ha-list-item>`,
            )}
          </ha-select>
        `;
      }
      return html`
        <select
          ?disabled=${disabled}
          .value=${value}
          @change=${(e) => onChange(e.target.value)}
        >
          ${options.map(
            (o) => html`<option value=${o.value} ?selected=${o.value === value}>${o.label}</option>`,
          )}
        </select>
      `;
    }
```

- [ ] **Step 2: Use it for the log-level selector** — replace the `<select>` block in `_renderHeader` (`fado-common.js:685-689`) with:

```js
            ${this._renderSelect({
              value: this._logLevel,
              options: [
                { value: "warning", label: "Warning" },
                { value: "info", label: "Info" },
                { value: "debug", label: "Debug" },
              ],
              onChange: (value) => this._saveLogLevel(value),
            })}
```

- [ ] **Step 3: Use it for the native-transitions selector** — replace the `<select class="native-transitions-select">` block in `_renderLightRow` (`fado-common.js:912-921`) with:

```js
            ${this._renderSelect({
              value: nativeTransitionsToValue(light.native_transitions),
              disabled: isExcluded,
              options: [
                { value: "", label: "" },
                { value: "true", label: "Yes" },
                { value: "false", label: "No" },
                { value: "disable", label: "Disable" },
              ],
              onChange: (value) =>
                this._handleNativeTransitionsValue(light.entity_id, value),
            })}
```

- [ ] **Step 4: Add the value-based handler and keep the event one** — add next to `_handleNativeTransitionsChange` (~line 637):

```js
    async _handleNativeTransitionsValue(entityId, value) {
      const nativeTransitions = valueToNativeTransitions(value);
      const light = this._findLight(entityId);
      if (light) light.native_transitions = nativeTransitions;
      await this.hass.callWS({
        type: "fado/save_light_config",
        entity_id: entityId,
        native_transitions: nativeTransitions,
      });
    }
```

Keep `_handleLogLevelChange`/`_handleNativeTransitionsChange` only if still referenced; otherwise delete them (the new helpers call `_saveLogLevel` / `_handleNativeTransitionsValue` directly). Grep first: `grep -n "_handleLogLevelChange\|_handleNativeTransitionsChange" custom_components/fado/frontend/fado-common.js`.

- [ ] **Step 5: Remove dead select CSS** — delete `.log-level-selector select` (none exists as a separate rule; the styling is via `.settings-row select`), `.settings-row select`, `.settings-row select:focus`, `.native-transitions-select`, `.native-transitions-select:focus`, `.native-transitions-select:disabled` from `fadoStyles`. Add minimal sizing:

```js
  ha-select { --mdc-menu-min-width: 120px; min-width: 120px; }
  .native-transitions ha-select,
  td.col-native-transitions ha-select { min-width: 110px; }
```

- [ ] **Step 6: Deploy and verify (visual gate)**

`cp to ha`, reload. Confirm: log-level select shows current level and changing it persists (reload keeps it); native-transitions select shows the right value per light, changing it saves, and it is disabled for excluded lights. Test in light + dark.

- [ ] **Step 7: Update CHANGES.md and commit**

Add under `## [Unreleased]` → `Changed`:

```
- Frontend: configuration panel/card now use HA's themed select control and a
  `--fado-*` design-token layer for consistent theming.
```

```bash
git add custom_components/fado/frontend/fado-common.js CHANGES.md
git commit -m "feat(frontend): migrate selects to ha-select with native fallback"
```

**END OF PR 1.** Open PR for `feat/frontend-design-overhaul` covering Tasks 1–5 (or continue and bundle with PR 2 per user preference).

---

# PHASE 2 — Responsive card view (PR 2)

### Task 6: `_compact` element-width flag + factor the table render

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

**Interfaces:**
- Produces: reactive `_compact` boolean; `_renderTableView()` (the current table+settings render) and `_renderSettingsCard()` extracted from `_renderContent`.

- [ ] **Step 1: Declare the property** — add `_compact: { type: Boolean, reflect: true, attribute: "compact" }` to `static get properties()` (~line 23) and `this._compact = false;` + `this._resizeObserver = null;` in the constructor. Reflecting to a `compact` attribute on the host lets CSS scope the reflow to `:host([compact])`, keeping the single 720px element-width threshold (not a separate viewport `@media`).

- [ ] **Step 2: Attach a ResizeObserver** — in `connectedCallback` (after the existing setup):

```js
      this._resizeObserver = new ResizeObserver((entries) => {
        const width = entries[0]?.contentRect?.width ?? 0;
        const compact = width > 0 && width < 720;
        if (compact !== this._compact) this._compact = compact;
      });
      this._resizeObserver.observe(this);
```

In `disconnectedCallback`:

```js
      if (this._resizeObserver) {
        this._resizeObserver.disconnect();
        this._resizeObserver = null;
      }
```

- [ ] **Step 3: Extract `_renderSettingsCard()`** — move the second `<ha-card>` (the settings + diagnostics block, `fado-common.js:772-792`) out of `_renderContent` into:

```js
    _renderSettingsCard() {
      return html`
        <ha-card>
          <div class="settings-row">
            <label>Global min delay:</label>
            ${this._renderNumberInput({
              value: this._globalMinDelayMs || "",
              min: 50, max: 2000, step: 10, suffix: "ms",
              onChange: (e) => this._handleGlobalDelayChange(e),
            })}
            <span class="hint">The absolute minimum delay for all lights</span>
          </div>
          ${this._entryId ? html`
            <div class="settings-row">
              <a href="#" @click=${(e) => { e.preventDefault(); this._downloadDiagnostics(); }}>
                <ha-icon icon="mdi:download" style="--mdc-icon-size: 18px; vertical-align: middle; margin-right: 4px;"></ha-icon>Download diagnostics
              </a>
            </div>
          ` : ""}
        </ha-card>
      `;
    }
```

- [ ] **Step 4: Extract `_renderTableView()`** — move the table `<ha-card>` (`fado-common.js:749-771`) into `_renderTableView()` returning the table card followed by `${this._renderSettingsCard()}`.

- [ ] **Step 5: Switch in `_renderContent`** — replace the final `return html\`${this._renderHeader()} <ha-card>...table...</ha-card> <ha-card>...settings...</ha-card>\`;` with:

```js
      return html`
        ${this._renderHeader()}
        ${this._compact ? this._renderCardView() : this._renderTableView()}
      `;
```

- [ ] **Step 6: Temporary stub** — add a stub so it compiles before Task 7:

```js
    _renderCardView() {
      return this._renderTableView();
    }
```

- [ ] **Step 7: Deploy and verify (visual gate)**

`cp to ha`. At desktop width the table renders unchanged. Narrow the window below 720px (or use the card in a narrow dashboard section): still the table for now (stub), and no console errors. Confirm `_compact` flips (temporarily `console.log` it, then remove).

- [ ] **Step 8: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js
git commit -m "feat(frontend): add _compact width flag and factor table render"
```

---

### Task 7: `_renderCardView()` — collapsible per-light cards

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

**Interfaces:**
- Consumes: `collapseKeyForArea`, `collapseKeyForLight`, `getCheckboxState`, `getExcludeState`, `areaNeedsSetupCount`, `needsSetupLabel`, `needsSetup`, `nativeTransitionsToValue`.

- [ ] **Step 1: Replace the stub `_renderCardView`** with the real implementation:

```js
    _renderCardView() {
      return html`
        ${this._data.areas.map((area) => this._renderAreaCard(area))}
        ${this._renderSettingsCard()}
      `;
    }

    _renderAreaCard(area) {
      const areaKey = collapseKeyForArea(area);
      const isCollapsed = this._collapsed[areaKey];
      const areaIcon = area.icon || "mdi:texture-box";
      const setupLabel = needsSetupLabel(areaNeedsSetupCount(area));
      const areaLightIds = this._getAreaLightIds(area);
      const configureState = this._getCheckboxState(areaLightIds);
      const excludeState = this._getExcludeState(area.lights);
      return html`
        <ha-card class="area-card">
          <div class="area-card-header" @click=${() => this._toggleCollapse(areaKey)}>
            <ha-icon class="chevron ${isCollapsed ? "collapsed" : ""}" icon="mdi:chevron-down"></ha-icon>
            <ha-icon class="header-icon" icon="${areaIcon}"></ha-icon>
            <span class="area-name">${area.name}</span>
            ${setupLabel ? html`<span class="needs-setup-rollup">· ${setupLabel}</span>` : ""}
            <span class="spacer"></span>
            <span class="area-card-check" @click=${(e) => e.stopPropagation()}>
              <span class="mini-label">Exclude</span>
              <ha-checkbox
                .checked=${excludeState === "all"}
                .indeterminate=${excludeState === "some"}
                @change=${(e) => this._handleAreaExcludeChange(area, e)}
              ></ha-checkbox>
            </span>
            <span class="area-card-check" @click=${(e) => e.stopPropagation()}>
              <span class="mini-label">Configure</span>
              <ha-checkbox
                .checked=${configureState === "all"}
                .indeterminate=${configureState === "some"}
                @change=${(e) => this._handleAreaCheckboxChange(area, e)}
              ></ha-checkbox>
            </span>
          </div>
          ${isCollapsed
            ? ""
            : area.lights.length > 0
              ? area.lights.map((light) => this._renderLightCard(light))
              : html`<div class="no-lights card-no-lights">No lights in this area</div>`}
        </ha-card>
      `;
    }

    _renderLightCard(light) {
      const lightKey = collapseKeyForLight(light.entity_id);
      const isCollapsed = this._collapsed[lightKey];
      const lightIcon = light.icon || "mdi:lightbulb";
      const state = this.hass.states[light.entity_id];
      const isOn = state && state.state === "on";
      const isTesting = this._testing.has(light.entity_id);
      const errorMessage = this._testErrors.get(light.entity_id);
      const isExcluded = light.exclude;
      const flagSetup = needsSetup(light);
      return html`
        <div class="light-card ${isExcluded ? "excluded" : ""}">
          <div class="light-card-header" @click=${() => this._toggleCollapse(lightKey)}>
            <ha-icon class="chevron ${isCollapsed ? "collapsed" : ""}" icon="mdi:chevron-down"></ha-icon>
            <ha-icon class="light-icon ${isOn ? "on" : ""}" icon="${lightIcon}"></ha-icon>
            <div class="light-info">
              <div class="light-name">${light.name}</div>
              <div class="light-substatus">
                ${flagSetup
                  ? html`<span class="needs-setup">● Needs setup</span>`
                  : html`<span class="entity-id">${light.min_delay_ms ? `${light.min_delay_ms} ms` : light.entity_id}</span>`}
              </div>
            </div>
            <span class="spacer"></span>
            <span class="light-card-check" @click=${(e) => e.stopPropagation()}>
              <ha-checkbox
                ?disabled=${isTesting || isExcluded}
                .checked=${this._configureChecked.has(light.entity_id)}
                @change=${(e) => this._handleConfigureChange(light.entity_id, e)}
              ></ha-checkbox>
            </span>
          </div>
          ${isCollapsed ? "" : html`
            <div class="light-card-body">
              <div class="field-row" @click=${() => this._openLightDialog(light.entity_id)}>
                <span class="field-label">Entity</span>
                <span class="entity-id">${light.entity_id}</span>
              </div>
              <div class="field-row">
                <span class="field-label">Min delay</span>
                ${isTesting
                  ? html`<div class="testing-spinner"><div class="spinner"></div></div>`
                  : html`${this._renderNumberInput({
                      value: light.min_delay_ms || "",
                      min: this._globalMinDelayMs, max: 2000, step: 10,
                      disabled: isExcluded, suffix: "ms",
                      onChange: (e) => this._handleDelayChange(light.entity_id, e),
                    })}`}
              </div>
              ${errorMessage ? html`<div class="test-error">${errorMessage}</div>` : ""}
              <div class="field-row">
                <span class="field-label">Min brightness</span>
                <span>${light.min_brightness != null ? light.min_brightness : "—"}</span>
              </div>
              <div class="field-row">
                <span class="field-label">Native transitions</span>
                ${this._renderSelect({
                  value: nativeTransitionsToValue(light.native_transitions),
                  disabled: isExcluded,
                  options: [
                    { value: "", label: "" },
                    { value: "true", label: "Yes" },
                    { value: "false", label: "No" },
                    { value: "disable", label: "Disable" },
                  ],
                  onChange: (value) => this._handleNativeTransitionsValue(light.entity_id, value),
                })}
              </div>
              <div class="field-row">
                <span class="field-label">Exclude</span>
                <ha-checkbox
                  .checked=${light.exclude}
                  @change=${(e) => this._handleCheckboxChange(light.entity_id, "exclude", e)}
                ></ha-checkbox>
              </div>
            </div>
          `}
        </div>
      `;
    }
```

- [ ] **Step 2: Add card-view CSS** to `fadoStyles`:

```js
  .area-card { margin-bottom: var(--fado-space-4); }
  .area-card-header {
    display: flex; align-items: center; gap: var(--fado-space-2);
    padding: var(--fado-space-3) var(--fado-space-4);
    background: var(--fado-surface-2); cursor: pointer; user-select: none;
    font-weight: 500;
  }
  .area-card-header .area-name { font-weight: 500; }
  .needs-setup-rollup { color: var(--fado-warning); font-size: var(--fado-font-sm); }
  .spacer { flex: 1; }
  .area-card-check, .light-card-check { display: flex; align-items: center; }
  .mini-label { font-size: var(--fado-font-sm); color: var(--fado-text-muted); margin-right: var(--fado-space-1); }

  .light-card { border-top: 1px solid var(--fado-border); }
  .light-card.excluded .light-card-body,
  .light-card.excluded .light-name { opacity: 0.5; }
  .light-card-header {
    display: flex; align-items: center; gap: var(--fado-space-2);
    padding: var(--fado-space-2) var(--fado-space-4); cursor: pointer;
  }
  .light-substatus { font-size: var(--fado-font-sm); color: var(--fado-text-muted); }
  .needs-setup { color: var(--fado-warning); }
  .light-card-body { padding: 0 var(--fado-space-4) var(--fado-space-3) var(--fado-space-4); }
  .field-row {
    display: flex; align-items: center; justify-content: space-between;
    gap: var(--fado-space-3); padding: var(--fado-space-1) 0;
    min-height: var(--fado-control-height);
  }
  .field-label { color: var(--fado-text-muted); }
  .card-no-lights { padding: var(--fado-space-3) var(--fado-space-4); }
```

- [ ] **Step 3: Deploy and verify (visual gate)**

`cp to ha`. Narrow below 720px: areas render as cards; each light is a collapsed row showing name + status/needs-setup + configure checkbox; tapping a light expands its fields; min-delay edit saves; native-transitions select saves and disables when excluded; exclude dims the card; Autoconfigure spinner shows in the Min-delay row. Test light + dark.

- [ ] **Step 4: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js
git commit -m "feat(frontend): collapsible per-light card view for narrow widths"
```

---

### Task 8: Per-card collapse persistence + STORAGE_VERSION bump

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

- [ ] **Step 1: Bump the storage version** — in `_loadCollapsedState` change `const STORAGE_VERSION = 2;` to `const STORAGE_VERSION = 3;` and in `_saveCollapsedState` change `_version: 2` to `_version: 3`.

- [ ] **Step 2: Seed light-card keys as collapsed by default** — in `_initCollapsedState`, inside the area loop, after the area-key seeding, add:

```js
          for (const light of area.lights) {
            const lightKey = collapseKeyForLight(light.entity_id);
            if (!(lightKey in newCollapsed)) {
              newCollapsed[lightKey] = true;
            }
          }
```

This makes light cards default-collapsed and lets the existing `_toggleCollapse` (which flips the stored boolean) expand/collapse and persist them, reusing the same `fado_collapsed` blob.

- [ ] **Step 3: Deploy and verify (visual gate)**

`cp to ha`. Narrow view: expand a couple of light cards, reload the page — the same cards stay expanded; collapse them, reload — they stay collapsed. Old `_version:2` blobs are discarded once (areas re-default to collapsed).

- [ ] **Step 4: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js
git commit -m "feat(frontend): persist per-card collapse state (storage v3)"
```

---

### Task 9: Needs-setup roll-up on the desktop table area header

The card view already shows the roll-up (Task 7). Mirror it on the table area row so desktop gets the same signal.

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

- [ ] **Step 1: Add the roll-up to `_renderAreaRows`** — in the `group-cell` div (`fado-common.js:807-811`), after `${area.name}`, add:

```js
              ${(() => { const l = needsSetupLabel(areaNeedsSetupCount(area)); return l ? html`<span class="needs-setup-rollup">· ${l}</span>` : ""; })()}
```

(`.needs-setup-rollup` CSS already added in Task 7.)

- [ ] **Step 2: Deploy and verify (visual gate)**

`cp to ha`, desktop width. Area rows with unconfigured lights show "· N need setup" in the warning colour; configuring/excluding all of them removes it.

- [ ] **Step 3: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js
git commit -m "feat(frontend): show needs-setup roll-up on table area headers"
```

---

### Task 10: Responsive header/settings reflow + touch targets

CSS only. Gate: visual at narrow width.

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`

- [ ] **Step 1: Add `:host([compact])` reflow rules** at the END of `fadoStyles` (after all base rules). These key off the reflected `compact` attribute (Task 6 Step 1) so the reflow uses the same 720px element-width threshold as the table↔card switch — not a separate viewport `@media`. `:host([compact]) .x` also out-specifies the bare `.x` base rules, so order/cascade is safe:

```js
  :host([compact]) { padding: var(--fado-space-3); --fado-control-height: 44px; }
  :host([compact]) .controls-row { flex-direction: column; align-items: stretch; gap: var(--fado-space-2); }
  :host([compact]) .controls-row ha-button { width: 100%; }
  :host([compact]) .log-level-selector { justify-content: space-between; }
  :host([compact]) .header-row { margin-bottom: var(--fado-space-3); }
  :host([compact]) .settings-row { flex-wrap: wrap; gap: var(--fado-space-2); padding: var(--fado-space-3); }
  :host([compact]) .settings-row ha-textfield,
  :host([compact]) .settings-row ha-input { width: 100%; }
  :host([compact]) .field-row ha-select,
  :host([compact]) .field-row ha-input,
  :host([compact]) .field-row ha-textfield { min-width: 140px; }
  :host([compact]) ha-checkbox { --mdc-checkbox-ripple-size: 44px; }
```

- [ ] **Step 2: Deploy and verify (visual gate)**

`cp to ha`, narrow below 720px (and on a real phone if possible). Header controls stack full-width; Autoconfigure button spans the width; settings rows wrap; checkboxes/inputs/selects are comfortable thumb targets (~44px). Cross-check desktop is unaffected.

- [ ] **Step 3: Update CHANGES.md and commit**

Add under `## [Unreleased]` → `Added`:

```
- Frontend: responsive layout — on narrow screens the lights table becomes
  collapsible per-light cards with a "needs setup" indicator and a per-area
  roll-up; touch-friendly controls.
```

```bash
git add custom_components/fado/frontend/fado-common.js CHANGES.md
git commit -m "feat(frontend): responsive header/settings reflow and touch targets"
```

**END OF PR 2.**

---

# PHASE 3 — Docs (fold into PR 2 or a small PR 3)

### Task 11: `design-system.md` + CLAUDE.md pointer

**Files:**
- Create: `docs/developers/design-system.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write `docs/developers/design-system.md`** with these sections (real content, not placeholders):
  - **Tokens** — the full `--fado-*` list from `fadoTokens` with what each maps to.
  - **Controls** — use eager `ha-*` directly; `ha-select`/`ha-input` via the guarded `_renderSelect`/`_renderNumberInput` helpers (registered-or-fallback); `e.stopPropagation()` on re-emit; no raw `title=`.
  - **Responsive** — `_compact` ResizeObserver at 720px element width, reflected to a `compact` host attribute; table ↔ collapsible-card switch; reflow CSS scoped to `:host([compact])` (NOT a viewport `@media`, so a narrow card on a wide screen reflows correctly); `--fado-control-height: 44px` when compact.
  - **Needs-setup indicator** — `needsSetup(light)` predicate, amber dot + text, area roll-up via `areaNeedsSetupCount`/`needsSetupLabel`.
  - **Logic module** — `fado-logic.js` is lit-free and unit-tested with vitest (`npm test`); put new pure logic there.
  - **No-build note** — lit from unpkg CDN; no bundle step; deploy with the devcontainer copy command.

- [ ] **Step 2: Add a pointer to `CLAUDE.md`** under a new `## Frontend design system` heading:

```
## Frontend design system

The frontend uses a `--fado-*` token layer and conventions documented in
`docs/developers/design-system.md`. Follow it: use the `--fado-*` tokens (never
hardcode chrome colour/spacing), the guarded `ha-*` control helpers, and the
720px `_compact` breakpoint. Pure logic goes in `fado-logic.js` with a vitest
test (`npm test`).
```

- [ ] **Step 3: Commit**

```bash
git add docs/developers/design-system.md CLAUDE.md
git commit -m "docs: add frontend design-system reference and CLAUDE.md pointer"
```

---

## Final verification (before opening/merging PRs)

- [ ] `npm test` — all `fado-logic` tests green.
- [ ] `ruff check .` && `ruff format .` && `npx pyright` — clean.
- [ ] Visual pass: panel **and** card; light + dark + custom theme; desktop (table) and narrow (cards); confirm select save, needs-setup dot + roll-up, per-card collapse persistence, touch targets, no Autoconfigure/exclude regressions.
- [ ] `CHANGES.md` Unreleased section reflects the user-facing changes.

## Self-review notes (coverage)

- Spec §1 tokens → Task 4. §2 ha-select → Task 5. §3 font vars → Task 4 Step 1/3.
  §4 responsive → Tasks 6–10. §5 logic+tests → Tasks 1–3. §6 docs → Task 11.
- All function names used in later tasks (`needsSetup`, `getCheckboxState`,
  `collapseKeyForLight`, `nativeTransitionsToValue`, `_renderSelect`,
  `_renderSettingsCard`, `_renderCardView`) are defined in earlier tasks.
- Behaviour-preserving: handler signatures (`_handleAreaExcludeChange`,
  `_handleConfigureChange`, `_handleDelayChange`, `_handleCheckboxChange`) reused
  unchanged; only `native_transitions` gains a parallel value-based handler.
