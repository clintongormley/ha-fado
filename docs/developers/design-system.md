# Fado Frontend Design System

The Fado frontend (sidebar panel + Lovelace card) shares a single design system
defined in `custom_components/fado/frontend/fado-common.js`. This document
describes the conventions; follow them when editing or extending the UI.

---

## 1. Token layer (`--fado-*`)

Colour and structural values are defined in `fadoTokens` (a Lit `css` block
applied at `:host`). Prefer `--fado-*` tokens and avoid introducing **new**
hardcoded hex colours, pixel spacing, or font sizes in component styles. Some
legacy `px` literals remain in `fadoStyles` (e.g. `:host { padding: 16px; }`,
table cell padding) and are migrated to tokens opportunistically.

### Colour tokens

| Token | Maps to (with fallback) |
|---|---|
| `--fado-accent` | `var(--primary-color, #03a9f4)` |
| `--fado-warning` | `var(--warning-color, #e09112)` |
| `--fado-error` | `var(--error-color, #db4437)` |
| `--fado-on` | `var(--amber-color, #ffc107)` — lit-bulb "on" colour |
| `--fado-on-accent` | `var(--text-primary-color, #fff)` — text on accent backgrounds |
| `--fado-text` | `var(--primary-text-color)` |
| `--fado-text-muted` | `var(--secondary-text-color)` |
| `--fado-border` | `var(--divider-color)` |
| `--fado-surface` | `var(--card-background-color)` |
| `--fado-surface-2` | `var(--secondary-background-color, rgba(0,0,0,0.05))` |
| `--fado-disabled` | `var(--disabled-text-color)` — disabled `ha-button` colour |

### Structural tokens

These are fixed values but can be overridden by a parent page at the `:host`
boundary.

| Token | Default |
|---|---|
| `--fado-space-1` | `4px` |
| `--fado-space-2` | `8px` |
| `--fado-space-3` | `12px` |
| `--fado-space-4` | `16px` |
| `--fado-space-5` | `24px` |
| `--fado-space-6` | `32px` |
| `--fado-radius` | `8px` |
| `--fado-radius-sm` | `4px` |
| `--fado-font-sm` | `var(--ha-font-size-s, var(--paper-font-caption_-_font-size, 12px))` |
| `--fado-font-md` | `var(--ha-font-size-m, var(--paper-font-body1_-_font-size, 14px))` |
| `--fado-font-lg` | `20px` |
| `--fado-font-h1` | `var(--ha-card-header-font-size, 24px)` |
| `--fado-font-family` | `var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, sans-serif))` |
| `--fado-control-height` | `40px` (bumped to `44px` in compact mode — see §3) |

---

## 2. Controls

### Eagerly-registered `ha-*` elements (use directly)

HA registers these elements before the panel module is imported, so they are
always available without any guard:

- `ha-card`, `ha-button`, `ha-icon`, `ha-icon-button`
- `ha-checkbox`, `ha-formfield`

Use them exactly as they appear in HA's own panels. Do **not** hand-roll a
`<button>`, `<input type="checkbox">`, or icon in new code.

### `ha-select` and `ha-input` — guarded helpers

Some HA controls (`ha-select`, `ha-input`) are registered lazily and may not be
present on older HA versions. The mixin provides two helper methods that detect
availability at render time and fall back to the nearest native element:

**`_renderSelect({ value, options, disabled, onChange })`**

- If `customElements.get("ha-select")` is defined: renders `<ha-select>` with
  `<ha-list-item>` children.
- Otherwise: renders a native `<select>`.
- Always calls `e.stopPropagation()` on the `selected` and `closed` events
  before invoking `onChange`, because HA composed events cross shadow-DOM
  boundaries and would double-fire without it.

```js
this._renderSelect({
  value: nativeTransitionsToValue(light.native_transitions),
  options: [
    { value: "true",    label: "Yes" },
    { value: "false",   label: "No" },
    { value: "disable", label: "Disable" },
  ],
  onChange: (value) => this._handleNativeTransitionsValue(light.entity_id, value),
})
```

**`_renderNumberInput({ value, min, max, step, placeholder, disabled, suffix, onChange })`**

- If `customElements.get("ha-input")` is defined: renders `<ha-input
  type="number">` (Web Awesome / HA 2025+).
- Otherwise: renders `<ha-textfield type="number">` (Material Design / older
  HA).
- The `onChange` callback receives the raw DOM event; read `e.target.value`.

```js
this._renderNumberInput({
  value: light.min_delay_ms || "",
  min: this._globalMinDelayMs, max: 2000, step: 10, suffix: "ms",
  onChange: (e) => this._handleDelayChange(light.entity_id, e),
})
```

### General control rules

- **No raw `title=` attributes.** HA components carry their own accessible
  labels; adding a `title` creates a double tooltip. Use `aria-label` only when
  no visible label is present.
- **Always call `e.stopPropagation()`** when re-emitting a `value-changed` or
  similar composed event from within a wrapper — composed events cross
  shadow-DOM boundaries and will double-fire if not stopped.

---

## 3. Responsive layout — `_compact` and `:host([compact])`

### Breakpoint mechanism

The mixin attaches a `ResizeObserver` to the host element in
`connectedCallback`:

```js
this._resizeObserver = new ResizeObserver((entries) => {
  const width = entries[0]?.contentRect?.width ?? 0;
  const compact = width > 0 && width < 720;
  if (compact !== this._compact) this._compact = compact;
});
this._resizeObserver.observe(this);
```

Key details:
- The threshold is **720 px of *element* width** — not viewport width. A Fado
  card placed in a narrow Lovelace column on a wide-screen browser will reflow
  to compact; a panel that fills a wide browser will stay in table mode.
- `_compact` is declared with `reflect: true, attribute: "compact"` so Lit
  reflects it to the host as a boolean attribute. All responsive CSS is scoped
  to `:host([compact])`, not `@media` queries.
- The observer is disconnected in `disconnectedCallback` to avoid leaks.

### Layout switch

`_renderContent()` branches on `this._compact`:

```js
return html`
  ${this._renderHeader()}
  ${this._compact ? this._renderCardView() : this._renderTableView()}
`;
```

- **`_renderTableView()`** — a single `<ha-card>` wrapping a full `<table>`
  with one row per light, one sub-header row per area.
- **`_renderCardView()`** — one collapsible `<ha-card>` per area, each
  containing collapsible light cards with labelled field rows.

### Compact-mode CSS

All compact adjustments live in `fadoStyles` under `:host([compact])` selectors:

```css
:host([compact]) { padding: var(--fado-space-3); --fado-control-height: 44px; }
:host([compact]) .controls-row { flex-direction: column; align-items: stretch; gap: var(--fado-space-2); }
:host([compact]) .controls-row ha-button { width: 100%; }
:host([compact]) .header-row { margin-bottom: var(--fado-space-3); }
:host([compact]) .settings-row { flex-wrap: wrap; gap: var(--fado-space-2); padding: var(--fado-space-3); }
:host([compact]) .settings-row ha-textfield,
:host([compact]) .settings-row ha-input { width: 100%; }
:host([compact]) .field-row ha-select,
:host([compact]) .field-row ha-input,
:host([compact]) .field-row ha-textfield { min-width: 140px; }
:host([compact]) ha-checkbox { --mdc-checkbox-ripple-size: 44px; }
```

Note that `--fado-control-height` is overridden to **44 px** in compact mode,
giving touch-friendly tap targets. The `.field-row` min-height is driven by
this token:

```css
.field-row { min-height: var(--fado-control-height); }
```

---

## 4. Needs-setup indicator

A light "needs setup" when it has no `min_delay_ms` configured and is not
excluded. The predicate and its area roll-up live in `fado-logic.js`:

```js
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
```

### Per-light indicator

In the card view each light header shows a coloured sub-status line:

```html
<!-- flagSetup = needsSetup(light) -->
${flagSetup
  ? html`<span class="needs-setup">● Needs setup</span>`
  : html`<span class="entity-id">${light.min_delay_ms ? `${light.min_delay_ms} ms` : light.entity_id}</span>`}
```

The `.needs-setup` class colours the dot amber via `var(--fado-warning)`.

### Area roll-up

Both the table view (area header row) and the card view (area card header) show
the roll-up label:

```html
${setupLabel ? html`<span class="needs-setup-rollup">· ${setupLabel}</span>` : ""}
```

`setupLabel` is obtained via:
```js
const setupLabel = needsSetupLabel(areaNeedsSetupCount(area));
```

The `.needs-setup-rollup` class also uses `var(--fado-warning)` but at
`var(--fado-font-sm)` size, so it reads as a secondary annotation.

---

## 5. Logic module (`fado-logic.js`)

`custom_components/fado/frontend/fado-logic.js` contains **all pure, stateless
logic** that does not touch the DOM or Lit:

- `needsSetup(light)` — needs-setup predicate (see §4).
- `areaNeedsSetupCount(area)` — area roll-up count.
- `needsSetupLabel(count)` — human-readable area label.
- `getCheckboxState(entityIds, configureChecked)` — tri-state (`"none"` /
  `"some"` / `"all"`) for the configure checkboxes.
- `getExcludeState(lights)` — tri-state for the exclude checkboxes.
- `collapseKeyForArea(area)` — `localStorage` key for area collapse state.
- `collapseKeyForLight(entityId)` — `localStorage` key for light collapse state.
- `nativeTransitionsToValue(nt)` — `native_transitions` config value → select
  string value (`true`/`false`/`"disable"`/`""`).
- `valueToNativeTransitions(value)` — inverse mapping.

**Rule:** any new pure logic (predicates, string formatters, state derivations)
goes in `fado-logic.js`, not in the mixin. This keeps it unit-testable.

The test suite lives at the repo root (`tests/frontend/fado-logic.test.js` or
similar) and runs with:

```bash
npm test        # vitest run — all 15 tests in one pass, ~200 ms
npm run test:watch  # interactive watch mode during development
```

No DOM or browser environment is needed — vitest's `happy-dom` environment is
available but the logic module itself imports nothing from the browser.

---

## 6. No-build frontend

The Fado frontend has **no build step**. Lit is loaded directly from the unpkg
CDN:

```js
import { LitElement, html, css }
  from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";
```

This means:

- There is no transpile / bundle / minify step.
- Editing a `.js` file in `custom_components/fado/frontend/` and doing a **hard
  browser refresh** (`Cmd/Ctrl + Shift + R`) picks up the change immediately —
  no `npm run build`.
- In a devcontainer worktree the frontend directory is live-mounted into the HA
  container via:

  ```bash
  rm -Rf /workspaces/homeassistant-core/config/custom_components/fado \
    && cp -r /workspaces/ha-fado/custom_components/fado \
         /workspaces/homeassistant-core/config/custom_components/
  ```

  Run this after any Python or JS change so the running HA instance picks up
  your edits. (Pre-approved in `CLAUDE.local.md` — run without asking.)
- The only `npm` usage is the vitest test runner for `fado-logic.js`; it does
  not touch the frontend JS files served to the browser.
