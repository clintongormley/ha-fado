# Fado frontend design overhaul — design spec

**Date:** 2026-06-19
**Status:** Approved (brainstorm complete, awaiting spec review)

## Background

The Fado frontend is a small, build-less, vanilla-JS surface: `lit-element@2.4.0`
loaded from a unpkg CDN at runtime, no `package.json`, no TypeScript, no bundle. It is
essentially **one view** — a lights-configuration table plus a settings card — shared
by the sidebar panel (`panel.js`) and the Lovelace card (`fado-card.js`) via
`FadoCoreMixin` in `custom_components/fado/frontend/fado-common.js` (~1230 lines). A
dashboard strategy (`fado-strategy.js`) wraps the card.

It already follows most HA-panel conventions: real `ha-*` elements, theme vars with
fallbacks, the `ha-input`/`ha-textfield` registered-or-fallback guard, card-as-resource
registration (`card_resources.py`), and `getGridOptions()`.

This overhaul is a **right-sized subset** of the EPP Grid playbook — not a wholesale
port. EPP's playbook assumes a TS/Lit/npm build with many views, dialogs, and a
canvas/hero; Fado has none of that.

### Audit findings (what motivates the work)

| Check | Result | Verdict |
|---|---|---|
| Raw `<button>` vs `ha-button` | 0 raw, 6 `ha-button` | clean |
| `title=` tooltips | 0 | clean |
| Hardcoded hex | `#ffc107`, `#db4437` — both have `var(--…, …)` fallbacks | ok |
| Mixed control systems | `ha-checkbox`/`ha-input`/`ha-textfield` good, **but two hand-rolled raw `<select>`** + ~40 lines of select CSS | **fix** |
| `@media` queries | **0** — 6-column table with `min-width` columns; mobile = sideways scroll | **biggest gap** |
| Legacy font vars | `--paper-font-*` throughout (deprecated; HA mid Material→Web Awesome migration) | **modernise** |
| Design tokens | none — scattered px literals, no scale | light token layer worth it |
| Hardcoded spinner colours | `rgba(255,255,255,.3)` + `white` on button spinner | minor, tokenise |

## Goals

1. A `--fado-*` token layer (colour → HA theme vars; structural fixed-but-overridable).
2. Migrate the two raw `<select>` to `ha-select`.
3. Modernise the deprecated `--paper-font-*` vars to `--ha-font-*` (old var as fallback).
4. Responsive pass: below a width threshold the lights table becomes **collapsible
   per-light cards** with a "needs setup" indicator and area-level roll-up.
5. Extract pure logic into a lit-free `fado-logic.js` module and unit-test it (vitest +
   happy-dom).
6. A concise `docs/developers/design-system.md` + a CLAUDE.md pointer.

## Non-goals (explicit)

- The EPP primitive-wrapper element layer (button/field/toggle/card/dialog). One view
  already on `ha-*`; no repetition to justify it.
- TS / npm-build / committed-bundle migration.
- Replacing `lit-element@2.4.0` from CDN with modern/local Lit (separate decision).
- Desktop-alignment / canvas / hero work — nothing to attach to.

## Behaviour-preserving constraint

No WebSocket message types, event names, handler signatures, entity keys, localStorage
semantics (beyond the documented version bump), or engine logic change. **Markup and
styling only**, plus the pure-logic extraction (same outputs).

---

## Design

### 1. Token layer — `fadoTokens`

A new exported `css` block applied at `:host`, prepended in `static get styles()` so it
returns `[fadoTokens, fadoStyles]` and cascades into the shadow root. Every colour token
maps to an HA theme var with its real value as fallback; structural tokens are 4px-based
and overridable.

**Colour**
- `--fado-accent: var(--primary-color, #03a9f4)`
- `--fado-warning: var(--warning-color, #e09112)`  *(the needs-setup amber)*
- `--fado-error: var(--error-color, #db4437)`
- `--fado-on: var(--amber-color, #ffc107)`  *(light-on icon)*
- `--fado-text: var(--primary-text-color)`
- `--fado-text-muted: var(--secondary-text-color)`
- `--fado-border: var(--divider-color)`
- `--fado-surface: var(--card-background-color)`
- `--fado-surface-2: var(--secondary-background-color, rgba(0,0,0,0.05))`

**Structural**
- spacing `--fado-space-1..6` = 4 / 8 / 12 / 16 / 24 / 32 px
- radius `--fado-radius` = 8px, `--fado-radius-sm` = 4px
- type `--fado-font-sm` = 13px, `--fado-font-md` = 14px, `--fado-font-lg` = 20px,
  `--fado-font-h1` = 24px
- `--fado-control-height` = 40px default, **44px when `_compact`** (set on the host)

Existing scattered px literals and the two hardcoded spinner colours are tokenised as the
surrounding rules are touched.

### 2. `<select>` → `ha-select`

Both selects become `ha-select` + `ha-list-item`:
- Log-level selector (`fado-common.js` ~L685): options `warning` / `info` / `debug`.
- Native-transitions selector (~L912): options `""` / `true` / `false` / `disable`,
  labels blank / Yes / No / Disable.

Same `@change` wiring and the same string values feed the existing
`_handleLogLevelChange` / `_handleNativeTransitionsChange`. Call `e.stopPropagation()` on
re-emit. Guard with `customElements.get("ha-select")` and fall back to the native
`<select>` for much-older HA (mirrors the existing `ha-input`/`ha-textfield` pattern).
Delete `.native-transitions-select`, `.settings-row select`, `.log-level-selector select`
CSS (~40 lines).

### 3. Modernise font vars

Replace, keeping the old var as the inner fallback so nothing changes on either HA
generation:
- `--paper-font-body1_-_font-size` → `var(--ha-font-size-m, var(--paper-font-body1_-_font-size, 14px))`
- `--paper-font-caption_-_font-size` → `var(--ha-font-size-s, var(--paper-font-caption_-_font-size, 12px))`
- `--paper-font-body1_-_font-family` → `var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, sans-serif))`

These fold into the §1 type-scale tokens (the tokens carry the nested fallback; rules
reference the token).

### 4. Responsive / mobile

**Switch mechanism.** A `ResizeObserver` on the host sets `_compact = true` when the
element's own content width drops below **720px** (the table's minimum comfortable width:
col sums ~710px). Element width — not viewport `matchMedia` — because Fado renders both as
a full-width panel and as a dashboard card that can be embedded narrow on a wide screen.
The matching visual `@media`/class rules key on the same 720px threshold. `_compact` is a
new reactive property, distinct from HA's `narrow`. Observer attached in
`connectedCallback`, disconnected in `disconnectedCallback`.

**Two render paths, one logic core.** `_renderContent()` chooses `_renderCardView()` when
`_compact`, else the existing table render (factored into `_renderTable()`). This is a
deliberate, minimal fork of *markup only*; per-card collapse is genuinely cleaner with a
real card than CSS-restyled `<td>`s. Data, handlers, event names, area grouping, and the
header/settings sections are shared. The table path is otherwise unchanged.

**Card view.** Lights grouped under the existing area headers (area collapse persists as
today). Each light is a **collapsible card**, collapsed by default:
- Collapsed shows: chevron · light icon + name · one-line status (`<n> ms`, or the
  needs-setup flag) · the **Configure checkbox** (so batch-select for Autoconfigure works
  without expanding).
- Expanded reveals: Min delay (number input) · Min brightness (read-only) · Native
  transitions (`ha-select`) · Exclude (`ha-checkbox`) · Configure (`ha-checkbox`), each on
  its own labelled row.
- Excluded cards keep the existing dimmed treatment.
- Testing/spinner and per-light error states render in the card the same way they do in
  the table row.

**Per-card collapse state.** Keyed `light_<entity_id>`, stored in the same
`fado_collapsed` localStorage blob as area keys; bump `STORAGE_VERSION` (2 → 3) so the new
shape resets cleanly. Default collapsed (absent key ⇒ collapsed). Toggling persists.

**Needs-setup indicator (style A).** On any light where `needsSetup(light)` is true
(`!min_delay_ms && !exclude`): `● Needs setup` rendered in `--fado-warning` (dot + text,
theme-safe, not colour-only), on both collapsed and expanded cards. **Rolled up to the
area header** as `· N need setup` (omitted when N = 0), so it shows even when the area is
collapsed. The roll-up appears in both the card view and the table area header.

**Header / settings reflow.** Below 720px the `controls-row` (title · log level ·
Autoconfigure) and the `settings-row`s stack vertically with reduced padding and
full-width controls.

**Touch targets.** Host sets `--fado-control-height: 44px` when `_compact`; number inputs,
`ha-select`, and checkbox hit areas are ≥44px in card rows.

### 5. Logic extraction + tests

New lit-free module `custom_components/fado/frontend/fado-logic.js` (no CDN import) so
vitest imports it without resolving the unpkg URL. The mixin imports from it. Pure
functions (explicit args, no `this`):

- `needsSetup(light)` → `!light.min_delay_ms && !light.exclude`
- `areaNeedsSetupCount(area)` → number of lights needing setup
- `needsSetupLabel(count)` → roll-up text: `""` when 0, `"1 needs setup"` when 1,
  else `"${count} need setup"` (pluralised, matching the existing `_getTestingText` style)
- `getCheckboxState(entityIds, configureChecked)` → `"none" | "some" | "all"`
- `getExcludeState(lights)` → `"none" | "some" | "all"`
- `collapseKeyForArea(area)` → `area_<area_id|none>`
- `collapseKeyForLight(entityId)` → `light_<entity_id>`
- `nativeTransitionsToValue(nt)` / `valueToNativeTransitions(value)` — the select mapping
  (`null`/`undefined` ↔ `""`, `true` ↔ `"true"`, `false` ↔ `"false"`, `"disable"` ↔ `"disable"`)

The existing mixin methods (`_getCheckboxState`, `_getExcludeState`, etc.) delegate to
these, preserving current behaviour.

**Toolchain.** Root `package.json` + `vitest` + `happy-dom` as devDependencies (outside
`custom_components/`; `node_modules` gitignored). Tests in `tests/frontend/*.test.js`
importing from `../../custom_components/fado/frontend/fado-logic.js`. **TDD: a failing
test precedes each extracted function.** CSS/layout correctness is verified by eye, not
unit tests (happy-dom does not compute CSS).

### 6. Docs

`docs/developers/design-system.md`: the actual `--fado-*` tokens, the `ha-select` /
`ha-input` registered-or-fallback convention, the `_compact` 720px breakpoint + card-view
rules, and the needs-setup indicator. Add a "Frontend design system" pointer to the repo
`CLAUDE.md`.

---

## Verification

- **Unit:** vitest suite green for all `fado-logic.js` functions (per-function TDD).
- **Visual (by eye):** panel + card, light + dark + a custom theme, at desktop (table) and
  narrow (cards) widths. Confirm: select migration renders/saves; needs-setup dot + area
  roll-up; per-card collapse persists across reload; touch targets ≥44px; header/settings
  stack; no regression to Autoconfigure batch flow or excluded dimming.
- `ruff check .` / `ruff format .` / `npx pyright` remain clean (no Python change expected,
  but run before any PR per repo convention).

## Phasing (reviewable PRs)

1. **Foundation** — `fado-logic.js` + extraction, `fadoTokens`, vitest setup + TDD tests,
   font-var modernisation, `ha-select` migration. No layout change.
2. **Responsive card view** — `_compact` ResizeObserver, `_renderCardView()`, per-card
   collapse + persistence bump, needs-setup indicator + area roll-up, header/settings
   reflow, touch targets.
3. **Docs** — `design-system.md` + CLAUDE.md pointer (may fold into PR 2).

## Risks / notes

- `ResizeObserver` fires on every resize; debounce or guard so it only flips the reactive
  property on threshold crossings, avoiding render churn.
- `STORAGE_VERSION` bump discards existing collapse prefs once — acceptable, low-value
  state.
- The `ha-select` fallback path must keep the native `<select>` behaviour identical for
  old-HA users.
- CHANGES.md gets an `Added`/`Changed` entry per the repo changelog rule.
