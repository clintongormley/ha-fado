# Frontend i18n + Translation-Request Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frontend i18n layer to the Fado panel/card, ship auto-translated UI catalogs for the 25 already-translated languages, and add a dismissable banner that nudges users on an unsupported language to request a translation via a prefilled GitHub issue.

**Architecture:** A new `fado-i18n.js` holds the embedded English catalog (source of truth + synchronous fallback), a pure `localize()`, and an async `loadCatalog()`. The shared `FadoCoreMixin` (`fado-common.js`) gains `_t()` and loads the active language's catalog into a reactive `_catalog` state. Per-language UI strings live in `frontend/translations/<lang>.json`. Pure detection/format/storage helpers live in `fado-logic.js`; a thin `<fado-lang-banner>` LitElement renders over them.

**Tech Stack:** Vanilla ES modules, `lit-element@2.4.0` (from unpkg CDN — **no build step**), vitest + happy-dom for tests, Home Assistant custom panel/card.

## Global Constraints

- **lit-element version: 2.4.0** (CDN). It has **no `willUpdate`** — use `update(changedProperties)` (set reactive props before `super.update()`) and `updated()`/`connectedCallback`, matching the existing code.
- **No build step.** Edit `.js` files directly; never reference a bundle/transpile step.
- **Repo:** `clintongormley/ha-fado`. **Product name (verbatim):** `Fado Light Fader`.
- **Do NOT touch** backend `custom_components/fado/translations/*.json` or `strings.json` — adding keys there breaks `check_translations.py` (and the `--strict` pre-push hook) and creates dead keys.
- **Design tokens:** style with `var(--fado-TOKEN, REAL_FALLBACK)`; never hardcode chrome hex/spacing. Tokens are inherited into child elements through the shadow boundary.
- **localStorage:** keys prefixed `fado_`, JSON-encoded, every access wrapped in try/catch.
- **Controls:** `ha-icon-button` is eagerly registered — use it directly. No raw `title=`; use `aria-label` when there is no visible label. Call `e.stopPropagation()` when handling/re-emitting composed events.
- **GitHub deep-link uses `?body=`** (prefills immediately, pre-merge), never `?template=`.
- **Detection = intersection:** a language is covered only if it is in **both** `BACKEND_LANGUAGES` **and** `FRONTEND_LANGUAGES`, each matched exact-then-base.
- **Coverage target:** >90% on new pure files. `npm test` green after every task.
- **Pure logic is unit-tested; Lit element rendering is not** (CDN Lit can't be imported by vitest). Push testable behaviour into pure functions.
- **Branch:** `feat/frontend-i18n-translation-banner`. Commit after every task. Never commit to `main`.

---

## File Structure

- **Create** `custom_components/fado/frontend/fado-i18n.js` — `EN` catalog, `localize()`, `defaultLocalize()`, `loadCatalog()`.
- **Create** `custom_components/fado/frontend/fado-lang-banner.js` — `<fado-lang-banner>` element.
- **Create** `custom_components/fado/frontend/translations/<lang>.json` × 24 — auto-translated UI catalogs.
- **Modify** `custom_components/fado/frontend/fado-logic.js` — detection, language arrays, display-name/url/split-message/dismissal helpers; change `needsSetupLabel` signature.
- **Modify** `custom_components/fado/frontend/fado-common.js` — imports, `_t`/`_catalog`/catalog-loading, string conversion, banner placement.
- **Create** `tests/frontend/fado-i18n.test.js` — `localize` + source-key-coverage.
- **Create** `tests/frontend/fado-i18n-catalogs.test.js` — per-file catalog validation (keys ⊆ EN, placeholders preserved).
- **Modify** `tests/frontend/fado-logic.test.js` — detection, helpers, dismissal, language-array coverage guards, updated `needsSetupLabel`.
- **Create** `.github/ISSUE_TEMPLATE/translation_request.md`.
- **Modify** `docs/developers/design-system.md`, `CHANGES.md`.

---

## Task 1: i18n core module (`fado-i18n.js`)

**Files:**
- Create: `custom_components/fado/frontend/fado-i18n.js`
- Test: `tests/frontend/fado-i18n.test.js`

**Interfaces:**
- Produces:
  - `EN` — the English catalog object (nested).
  - `localize(catalog, fallback, key, params) -> string` — dotted-key lookup in `catalog`, then `fallback`, then returns raw `key`; interpolates `{param}` from `params`.
  - `defaultLocalize(key, params) -> string` — `localize(EN, EN, key, params)`.
  - `loadCatalog(code) -> Promise<object|null>` — fetches `./translations/<code>.json` (exact→base), `null` for `en`/unknown/error.

- [ ] **Step 1: Write the failing test** — `tests/frontend/fado-i18n.test.js`

```js
import { describe, it, expect } from "vitest";
import { EN, localize, defaultLocalize } from "../../custom_components/fado/frontend/fado-i18n.js";

describe("localize", () => {
  const cat = { a: { b: "from cat" }, only: "cat only" };
  const fb = { a: { b: "from fb" }, only: "fb only", fbonly: "fallback value" };

  it("returns the catalog value for a nested key", () => {
    expect(localize(cat, fb, "a.b")).toBe("from cat");
  });
  it("falls back to the fallback catalog when missing in catalog", () => {
    expect(localize(cat, fb, "fbonly")).toBe("fallback value");
  });
  it("falls back to fallback when catalog is null", () => {
    expect(localize(null, fb, "only")).toBe("fb only");
  });
  it("returns the raw key when missing everywhere", () => {
    expect(localize(cat, fb, "no.such.key")).toBe("no.such.key");
  });
  it("interpolates {param} placeholders", () => {
    expect(localize({ k: "hi {name}, {n} items" }, {}, "k", { name: "Sam", n: 3 }))
      .toBe("hi Sam, 3 items");
  });
  it("leaves unknown placeholders untouched", () => {
    expect(localize({ k: "a {x} b" }, {}, "k", { y: 1 })).toBe("a {x} b");
  });
  it("does not treat a key whose value is an object as a leaf", () => {
    expect(localize({ a: { b: "x" } }, {}, "a")).toBe("a");
  });
});

describe("defaultLocalize / EN", () => {
  it("resolves a real EN key", () => {
    expect(defaultLocalize("header.title")).toBe("Fado Light Fader");
  });
  it("interpolates against EN", () => {
    expect(defaultLocalize("actions.autoconfigure_count", { count: 2 }))
      .toBe("Autoconfigure (2)");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- fado-i18n`
Expected: FAIL — cannot resolve `../../custom_components/fado/frontend/fado-i18n.js`.

- [ ] **Step 3: Write the implementation** — `custom_components/fado/frontend/fado-i18n.js`

```js
/**
 * Frontend i18n for the Fado panel/card.
 *
 * English is embedded here (the source of truth and the synchronous fallback),
 * so the UI renders correct English instantly with no fetch and no flash. Other
 * languages live as JSON under ./translations/ and are fetched on demand.
 *
 * `localize` is pure (unit-tested). `loadCatalog` performs IO and is not.
 */

export const EN = {
  header: { title: "Fado Light Fader" },
  states: {
    loading: "Loading...",
    auth_error: "Administrator access is required to configure Fado.",
    no_lights_found: "No lights found.",
    no_active_lights: "No active lights available",
    no_lights_in_area: "No lights in this area",
  },
  actions: {
    autoconfigure: "Autoconfigure",
    autoconfigure_count: "Autoconfigure ({count})",
    configuring_one: "Configuring {count} light... ({done}/{total})",
    configuring_other: "Configuring {count} lights... ({done}/{total})",
  },
  table: {
    min_delay: "Min Delay (ms)",
    min_brightness: "Min Brightness",
    native_transitions: "Native Transitions",
  },
  card: {
    entity: "Entity",
    min_delay: "Min delay",
    min_brightness: "Min brightness",
    native_transitions: "Native transitions",
  },
  labels: {
    exclude: "Exclude",
    configure: "Configure",
  },
  status: {
    needs_setup: "Needs setup",
    needs_setup_one: "{count} needs setup",
    needs_setup_other: "{count} need setup",
  },
  native_transitions: {
    yes: "Yes",
    no: "No",
    disable: "Disable",
  },
  units: { ms: "ms" },
  language_request: {
    message:
      "Your Home Assistant language is {language}, but {product} isn't available in it yet.",
    action: "Request a translation →",
    dismiss: "Dismiss",
  },
};

function lookup(obj, key) {
  if (!obj || typeof obj !== "object") return null;
  let cur = obj;
  for (const part of key.split(".")) {
    if (cur == null || typeof cur !== "object") return null;
    cur = cur[part];
  }
  return typeof cur === "string" ? cur : null;
}

/** Dotted-key lookup: catalog -> fallback -> raw key; interpolates {param}. */
export function localize(catalog, fallback, key, params) {
  let str = lookup(catalog, key);
  if (str == null) str = lookup(fallback, key);
  if (str == null) return key;
  if (params) {
    str = str.replace(/\{(\w+)\}/g, (m, name) =>
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : m,
    );
  }
  return str;
}

/** English localizer — the default when no active catalog is loaded. */
export function defaultLocalize(key, params) {
  return localize(EN, EN, key, params);
}

/**
 * Fetch the UI catalog for a language code (exact, then the base before "-").
 * Returns null for English (embedded), unknown languages, or any fetch error,
 * so the caller falls back to EN.
 */
export async function loadCatalog(code) {
  if (!code) return null;
  const candidates = [code, code.split("-")[0]];
  for (const candidate of candidates) {
    if (!candidate || candidate === "en") continue;
    try {
      const url = new URL(`./translations/${candidate}.json`, import.meta.url);
      const resp = await fetch(url);
      if (resp.ok) return await resp.json();
    } catch {
      // try the next candidate
    }
  }
  return null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- fado-i18n`
Expected: PASS (all `localize` + `defaultLocalize` cases).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/fado-i18n.js tests/frontend/fado-i18n.test.js
git commit -m "feat(frontend): add i18n core (EN catalog + localize + loader)"
```

---

## Task 2: Convert panel strings to `_t` (behaviour-preserving)

**Files:**
- Modify: `custom_components/fado/frontend/fado-common.js`
- Modify: `custom_components/fado/frontend/fado-logic.js` (`needsSetupLabel` signature)
- Modify: `tests/frontend/fado-logic.test.js` (updated `needsSetupLabel` test)
- Test (new): `tests/frontend/fado-i18n.test.js` (append source-key-coverage)

**Interfaces:**
- Consumes: `EN`, `localize`, `loadCatalog` (Task 1).
- Produces: mixin method `_t(key, params)`; reactive `_catalog`; `needsSetupLabel(count, t)` now takes a localizer.

- [ ] **Step 1: Write the failing test** — update `needsSetupLabel` test in `tests/frontend/fado-logic.test.js`

Replace the existing `it("labels with pluralisation", …)` block with:

```js
  it("labels with pluralisation via the injected localizer", () => {
    const t = (key, params) =>
      ({
        "status.needs_setup_one": `${params.count} needs setup`,
        "status.needs_setup_other": `${params.count} need setup`,
      })[key];
    expect(needsSetupLabel(0, t)).toBe("");
    expect(needsSetupLabel(1, t)).toBe("1 needs setup");
    expect(needsSetupLabel(3, t)).toBe("3 need setup");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- fado-logic`
Expected: FAIL — `needsSetupLabel` ignores the `t` argument (still returns hardcoded English / `t` is undefined).

- [ ] **Step 3: Update `needsSetupLabel`** in `custom_components/fado/frontend/fado-logic.js`

Replace:

```js
/** Roll-up label for an area header; "" when none need setup. */
export function needsSetupLabel(count) {
  if (!count) return "";
  if (count === 1) return "1 needs setup";
  return `${count} need setup`;
}
```

with:

```js
/** Roll-up label for an area header; "" when none need setup. `t` is a localizer. */
export function needsSetupLabel(count, t) {
  if (!count) return "";
  return count === 1
    ? t("status.needs_setup_one", { count })
    : t("status.needs_setup_other", { count });
}
```

- [ ] **Step 4: Run the `needsSetupLabel` test to verify it passes**

Run: `npm test -- fado-logic`
Expected: PASS for the pluralisation test (other suites unaffected).

- [ ] **Step 5: Wire `_t` + catalog loading into the mixin** — `custom_components/fado/frontend/fado-common.js`

Update the imports at the top. Replace:

```js
export { LitElement, html, css };
```

with (add the i18n import and the banner side-effect import — `fado-lang-banner.js` is created in Task 6; the import is harmless until then because nothing renders it yet, but to keep `npm`/browser happy add it in Task 6's step instead — for now add only the i18n import):

```js
import { EN, localize, loadCatalog } from "./fado-i18n.js";

export { LitElement, html, css };
```

Add `_catalog` to `static get properties()` (inside the returned object):

```js
        _catalog: { type: Object },
```

In the constructor, add (next to the other field initialisers):

```js
      this._catalog = null;
      this._catalogLang = null;
```

Add the localizer + loader methods (place them just above `// ── Rendering ──`):

```js
    // ── i18n ───────────────────────────────────────────────────

    _t(key, params) {
      return localize(this._catalog, EN, key, params);
    }

    async _maybeLoadCatalog() {
      const lang =
        this.hass?.locale?.language ?? this.hass?.language ?? "en";
      if (lang === this._catalogLang) return;
      this._catalogLang = lang;
      this._catalog = await loadCatalog(lang); // null -> EN fallback
    }
```

In `connectedCallback`, inside the existing `if (this.hass) { … }`, add `this._maybeLoadCatalog();`:

```js
      if (this.hass) {
        this._fetchAll();
        this._subscribeConfigUpdates();
        this._maybeLoadCatalog();
      }
```

In `updated(changedProperties)`, at the start of the `if (changedProperties.has("hass") && this.hass)` block, add `this._maybeLoadCatalog();` (before the reconnect logic):

```js
      if (changedProperties.has("hass") && this.hass) {
        this._maybeLoadCatalog();
        const isReconnect =
```

- [ ] **Step 6: Replace hardcoded strings with `_t`** in `custom_components/fado/frontend/fado-common.js`

Make these exact replacements (each produces identical English output):

1. Remove the module-level `NATIVE_TRANSITIONS_OPTIONS` const and add a method instead. Delete:

```js
const NATIVE_TRANSITIONS_OPTIONS = [
  { value: "", label: "" },
  { value: "true", label: "Yes" },
  { value: "false", label: "No" },
  { value: "disable", label: "Disable" },
];
```

Add this method just below `_t`/`_maybeLoadCatalog`:

```js
    _nativeTransitionsOptions() {
      return [
        { value: "", label: "" },
        { value: "true", label: this._t("native_transitions.yes") },
        { value: "false", label: this._t("native_transitions.no") },
        { value: "disable", label: this._t("native_transitions.disable") },
      ];
    }
```

2. `_getButtonText()` → replace body:

```js
    _getButtonText() {
      const c = this._configureChecked.size;
      return c > 0
        ? this._t("actions.autoconfigure_count", { count: c })
        : this._t("actions.autoconfigure");
    }
```

3. `_getTestingText()` → replace body:

```js
    _getTestingText() {
      const c = this._testing.size;
      return this._t(c === 1 ? "actions.configuring_one" : "actions.configuring_other", {
        count: c,
        done: this._completedTests,
        total: this._totalToTest,
      });
    }
```

4. Every `<h1>Fado Light Fader</h1>` (4 occurrences — `_renderHeader` and three branches of `_renderContent`) → `<h1>${this._t("header.title")}</h1>`.

5. `<span>Loading...</span>` → `<span>${this._t("states.loading")}</span>`.

6. `<p>Administrator access is required to configure Fado.</p>` → `<p>${this._t("states.auth_error")}</p>`.

7. `<p>No lights found.</p>` → `<p>${this._t("states.no_lights_found")}</p>`.

8. `<div class="empty-message">No active lights available</div>` → `<div class="empty-message">${this._t("states.no_active_lights")}</div>`.

9. Both `No lights in this area` occurrences:
   - table: `html`<tr><td colspan="6" class="no-lights">No lights in this area</td></tr>`` → `…>${this._t("states.no_lights_in_area")}</td></tr>``
   - card: `html`<div class="no-lights card-no-lights">No lights in this area</div>`` → `…>${this._t("states.no_lights_in_area")}</div>``

10. Table headers in `_renderTableView`:
    - `<th class="col-delay">Min Delay (ms)</th>` → `…>${this._t("table.min_delay")}</th>`
    - `<th class="col-min-brightness">Min Brightness</th>` → `…>${this._t("table.min_brightness")}</th>`
    - `<th class="col-native-transitions">Native Transitions</th>` → `…>${this._t("table.native_transitions")}</th>`
    - `<th class="col-exclude">Exclude</th>` → `…>${this._t("labels.exclude")}</th>`

11. Settings card (`_renderSettingsCard`):
    - `<label>Global min delay:</label>` → `<label>${this._t("settings.global_min_delay")}</label>` — and add `settings.global_min_delay`, `settings.global_min_delay_hint`, `settings.download_diagnostics` to EN (see Step 6a below).
    - `<span class="hint">The absolute minimum delay for all lights</span>` → `…>${this._t("settings.global_min_delay_hint")}</span>`
    - `…<ha-icon icon="mdi:download" …></ha-icon>Download diagnostics` → `…</ha-icon>${this._t("settings.download_diagnostics")}`
    - The settings min-delay input `suffix: "ms"` → `suffix: this._t("units.ms")`.

12. Card view labels (`_renderAreaCard`, `_renderLightCard`):
    - mini-label `<span class="mini-label">Exclude</span>` → `…>${this._t("labels.exclude")}</span>`
    - mini-label `<span class="mini-label">Configure</span>` → `…>${this._t("labels.configure")}</span>`
    - field `<span class="field-label">Entity</span>` → `…>${this._t("card.entity")}</span>`
    - field `<span class="field-label">Min delay</span>` → `…>${this._t("card.min_delay")}</span>`
    - field `<span class="field-label">Min brightness</span>` → `…>${this._t("card.min_brightness")}</span>`
    - field `<span class="field-label">Native transitions</span>` → `…>${this._t("card.native_transitions")}</span>`
    - field `<span class="field-label">Exclude</span>` → `…>${this._t("labels.exclude")}</span>`
    - light-card min-delay input `suffix: "ms"` → `suffix: this._t("units.ms")`.

13. Needs-setup per-light status (`_renderLightCard`):
    `html`<span class="needs-setup">● Needs setup</span>`` → `html`<span class="needs-setup">● ${this._t("status.needs_setup")}</span>``

14. `needsSetupLabel` call sites (`_renderAreaCard`, `_renderAreaRows`):
    `const setupLabel = needsSetupLabel(areaNeedsSetupCount(area));` → `const setupLabel = needsSetupLabel(areaNeedsSetupCount(area), (k, p) => this._t(k, p));`

15. Both `options: NATIVE_TRANSITIONS_OPTIONS,` (in `_renderLightCard` and `_renderLightRow`) → `options: this._nativeTransitionsOptions(),`.

- [ ] **Step 6a: Add the settings keys to EN** — `custom_components/fado/frontend/fado-i18n.js`

Add a `settings` block to `EN` (after `card`):

```js
  settings: {
    global_min_delay: "Global min delay:",
    global_min_delay_hint: "The absolute minimum delay for all lights",
    download_diagnostics: "Download diagnostics",
  },
```

- [ ] **Step 7: Add the source-key-coverage test** — append to `tests/frontend/fado-i18n.test.js`

```js
import { readFileSync } from "node:fs";

describe("source key coverage", () => {
  const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
  const sources = [
    read("../../custom_components/fado/frontend/fado-common.js"),
    read("../../custom_components/fado/frontend/fado-logic.js"),
    read("../../custom_components/fado/frontend/fado-lang-banner.js"),
  ].join("\n");
  // Collect every key passed to this._t("…") / this.localize("…") / the
  // injected `t("…")` localizer. The patterns are anchored so identifiers that
  // merely END in `t(` — e.g. `split("-")`, `.at(` — are NOT matched.
  const keys = new Set();
  const re = /(?:\._t|\.localize|(?<![\w.])t)\(\s*["'`]([\w.]+)["'`]/g;
  for (const m of sources.matchAll(re)) {
    keys.add(m[1]);
  }
  const has = (key) => {
    let cur = EN;
    for (const part of key.split(".")) {
      if (cur == null || typeof cur !== "object") return false;
      cur = cur[part];
    }
    return typeof cur === "string";
  };

  it("found a sensible number of keys", () => {
    expect(keys.size).toBeGreaterThan(15);
  });
  it("every key used in source exists in EN", () => {
    const missing = [...keys].filter((k) => !has(k));
    expect(missing).toEqual([]);
  });
});
```

NOTE: this test reads `fado-lang-banner.js`, created in Task 6. If executing strictly in order, create an empty placeholder now so the read does not throw:

```bash
printf '// placeholder — implemented in Task 6\n' > custom_components/fado/frontend/fado-lang-banner.js
```

- [ ] **Step 8: Run the full suite**

Run: `npm test`
Expected: PASS. (Coverage test confirms no key typos; `needsSetupLabel` test green.)

- [ ] **Step 9: Verify English output is unchanged**

Read each EN value against the original string it replaced (Step 6 list). Confirm byte-identical English. Optionally deploy and hard-refresh the panel (`cp to ha`) to eyeball it.

- [ ] **Step 10: Commit**

```bash
git add custom_components/fado/frontend/fado-common.js custom_components/fado/frontend/fado-logic.js custom_components/fado/frontend/fado-i18n.js custom_components/fado/frontend/fado-lang-banner.js tests/frontend/fado-logic.test.js tests/frontend/fado-i18n.test.js
git commit -m "feat(frontend): route panel UI strings through i18n (_t)"
```

---

## Task 3: Auto-translated UI catalogs (24 languages)

**Files:**
- Create: `custom_components/fado/frontend/translations/{bg,cs,da,de,es,fi,fr,hu,id,it,ja,ko,nb,nl,pl,pt,ro,sk,sl,sv,tr,uk,vi,zh-Hans}.json`
- Test: `tests/frontend/fado-i18n-catalogs.test.js`

**Interfaces:**
- Consumes: `EN` (Task 1) as the source structure.
- Produces: 24 JSON catalogs, each a subset of `EN`'s keys with identical placeholders.

- [ ] **Step 1: Write the failing validation test** — `tests/frontend/fado-i18n-catalogs.test.js`

```js
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { EN } from "../../custom_components/fado/frontend/fado-i18n.js";

const dir = new URL("../../custom_components/fado/frontend/translations/", import.meta.url);

function flatten(obj, prefix = "") {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") Object.assign(out, flatten(v, path));
    else out[path] = v;
  }
  return out;
}
const placeholders = (s) =>
  new Set([...String(s).matchAll(/\{(\w+)\}/g)].map((m) => m[1]));

const enFlat = flatten(EN);
const files = readdirSync(dir).filter((f) => f.endsWith(".json"));

describe("frontend catalogs", () => {
  it("ships exactly the 24 expected language files", () => {
    expect(files.map((f) => f.replace(/\.json$/, "")).sort()).toEqual(
      [
        "bg", "cs", "da", "de", "es", "fi", "fr", "hu", "id", "it", "ja",
        "ko", "nb", "nl", "pl", "pt", "ro", "sk", "sl", "sv", "tr", "uk",
        "vi", "zh-Hans",
      ].sort(),
    );
  });

  for (const file of files) {
    describe(file, () => {
      const data = JSON.parse(readFileSync(new URL(file, dir), "utf8"));
      const flat = flatten(data);
      it("is valid JSON with no keys outside EN", () => {
        const extra = Object.keys(flat).filter((k) => !(k in enFlat));
        expect(extra).toEqual([]);
      });
      it("preserves placeholders for every translated key", () => {
        const broken = Object.keys(flat).filter((k) => {
          const want = placeholders(enFlat[k]);
          const got = placeholders(flat[k]);
          return want.size !== got.size || [...want].some((p) => !got.has(p));
        });
        expect(broken).toEqual([]);
      });
    });
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- fado-i18n-catalogs`
Expected: FAIL — the `translations/` dir doesn't exist / has no files.

- [ ] **Step 3: Generate the 24 catalogs**

Dispatch parallel translation subagents (one per language, or batches) — e.g. via `superpowers:dispatching-parallel-agents`. Give each agent the **full `EN` object** and these rules:

- Output **only** valid JSON, same nested structure as `EN`.
- **Translate values only.** Keep all keys identical.
- **Preserve every `{placeholder}` verbatim** (`{count}`, `{done}`, `{total}`, `{language}`, `{product}`) — do not translate or reorder the braces' contents.
- Keep `{product}` referring to the product name; do **not** translate "Fado Light Fader" elsewhere — it is injected, not in the catalog.
- Keep the trailing `→` in `language_request.action` and the `●`-free `status.needs_setup` value.
- `units.ms` stays `"ms"` in every language.
- Match the language's own plural conventions for the `_one`/`_other` pair as closely as a two-form scheme allows.

Write each result to `custom_components/fado/frontend/translations/<lang>.json`. These are **AI-generated, pending native review** — flagged in CHANGES/docs (Task 7) and solicited by the banner.

- [ ] **Step 4: Run the validation test**

Run: `npm test -- fado-i18n-catalogs`
Expected: PASS — 24 files, no stray keys, all placeholders intact.

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/translations tests/frontend/fado-i18n-catalogs.test.js
git commit -m "feat(frontend): add AI-generated UI translation catalogs (24 langs, pending review)"
```

---

## Task 4: Language detection + coverage guards (`fado-logic.js`)

**Files:**
- Modify: `custom_components/fado/frontend/fado-logic.js`
- Test: `tests/frontend/fado-logic.test.js`

**Interfaces:**
- Produces:
  - `BACKEND_LANGUAGES` — string[] of backend translation codes.
  - `FRONTEND_LANGUAGES` — string[] of frontend UI codes (incl. `"en"`).
  - `getLanguageSupport(hass) -> { available, code, baseCode }`.

- [ ] **Step 1: Write the failing tests** — append to `tests/frontend/fado-logic.test.js` (and add the new names to the import at the top of the file)

```js
describe("getLanguageSupport", () => {
  const hass = (language, locale) => ({ language, locale });

  it("covered when both backend and frontend have the exact code", () => {
    const r = getLanguageSupport(hass("fr", { language: "fr" }));
    expect(r).toEqual({ available: true, code: "fr", baseCode: "fr" });
  });
  it("prefers hass.locale.language over hass.language", () => {
    expect(getLanguageSupport(hass("en", { language: "fr" })).code).toBe("fr");
  });
  it("covered via base for a region variant (pt-BR -> pt)", () => {
    const r = getLanguageSupport(hass("pt-BR"));
    expect(r).toEqual({ available: true, code: "pt-BR", baseCode: "pt" });
  });
  it("covered via base for en-GB -> en", () => {
    expect(getLanguageSupport(hass("en-GB")).available).toBe(true);
  });
  it("NOT covered for an unsupported language (el)", () => {
    expect(getLanguageSupport(hass("el")).available).toBe(false);
  });
  it("NOT covered for a script variant we don't ship (zh-Hant)", () => {
    // we ship zh-Hans, not bare zh, so zh-Hant is uncovered
    expect(getLanguageSupport(hass("zh-Hant")).available).toBe(false);
  });
  it("covered for the script we ship (zh-Hans)", () => {
    expect(getLanguageSupport(hass("zh-Hans")).available).toBe(true);
  });
  it("no nudge when the language is undeterminable", () => {
    expect(getLanguageSupport({}).available).toBe(true);
    expect(getLanguageSupport(undefined).available).toBe(true);
  });
});

describe("language coverage guards", () => {
  const langs = (rel) =>
    readdirSync(new URL(rel, import.meta.url))
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(/\.json$/, ""));

  it("BACKEND_LANGUAGES matches the backend translations folder", () => {
    expect([...BACKEND_LANGUAGES].sort()).toEqual(
      langs("../../custom_components/fado/translations/").sort(),
    );
  });
  it("FRONTEND_LANGUAGES matches the frontend catalogs plus embedded en", () => {
    const files = langs("../../custom_components/fado/frontend/translations/");
    expect([...FRONTEND_LANGUAGES].sort()).toEqual(["en", ...files].sort());
  });
});
```

Add to the top of the test file: `import { readdirSync } from "node:fs";`, and add `getLanguageSupport, BACKEND_LANGUAGES, FRONTEND_LANGUAGES` to the existing `fado-logic.js` import.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- fado-logic`
Expected: FAIL — `getLanguageSupport` / arrays not exported.

- [ ] **Step 3: Implement** — append to `custom_components/fado/frontend/fado-logic.js`

```js
// ── Language coverage ────────────────────────────────────────
// Two source-of-truth arrays, each guarded by a test against its folder so
// they cannot silently drift. "en" is in FRONTEND_LANGUAGES even though it
// has no file (English is embedded in fado-i18n.js).

export const BACKEND_LANGUAGES = [
  "bg", "cs", "da", "de", "en", "es", "fi", "fr", "hu", "id", "it", "ja",
  "ko", "nb", "nl", "pl", "pt", "ro", "sk", "sl", "sv", "tr", "uk", "vi",
  "zh-Hans",
];

export const FRONTEND_LANGUAGES = [
  "bg", "cs", "da", "de", "en", "es", "fi", "fr", "hu", "id", "it", "ja",
  "ko", "nb", "nl", "pl", "pt", "ro", "sk", "sl", "sv", "tr", "uk", "vi",
  "zh-Hans",
];

function covers(list, code, baseCode) {
  return list.includes(code) || list.includes(baseCode);
}

/**
 * Resolve the user's language and whether Fado is "translated" into it.
 * Covered = intersection: a backend translation AND a frontend UI catalog,
 * each matched exact-then-base. Undeterminable language -> available:true
 * (no nudge).
 */
export function getLanguageSupport(hass) {
  const code = hass?.locale?.language ?? hass?.language ?? null;
  if (!code) return { available: true, code: null, baseCode: null };
  const baseCode = code.split("-")[0];
  const available =
    covers(BACKEND_LANGUAGES, code, baseCode) &&
    covers(FRONTEND_LANGUAGES, code, baseCode);
  return { available, code, baseCode };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- fado-logic`
Expected: PASS (detection + both coverage guards).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/fado-logic.js tests/frontend/fado-logic.test.js
git commit -m "feat(frontend): language detection (intersection) with coverage guards"
```

---

## Task 5: Banner helpers — display name, URL, message split, dismissal (`fado-logic.js`)

**Files:**
- Modify: `custom_components/fado/frontend/fado-logic.js`
- Test: `tests/frontend/fado-logic.test.js`

**Interfaces:**
- Produces:
  - `languageDisplayName(code) -> string` (native → English → raw code).
  - `buildTranslationRequestUrl(code, displayName) -> string`.
  - `splitMessageParts(template, boldValues) -> Array<{text}|{bold}>`.
  - `LANG_DISMISSED_KEY` constant, `readDismissedLangRequests() -> string[]`, `isLangRequestDismissed(code) -> boolean`, `persistDismissedLangRequest(code) -> void`.

- [ ] **Step 1: Write the failing tests** — append to `tests/frontend/fado-logic.test.js` (add the new names to the import)

```js
describe("languageDisplayName", () => {
  it("returns a native display name for a known language", () => {
    // fr in fr -> "français" (capitalisation varies by ICU; just assert non-code)
    const name = languageDisplayName("fr");
    expect(typeof name).toBe("string");
    expect(name).not.toBe("fr");
    expect(name.toLowerCase()).toContain("fran");
  });
  it("falls back to the raw code for an unknown tag (Intl echoes the code)", () => {
    // Intl.DisplayNames defaults to fallback:'code' so 'tlh' would echo back;
    // the guard must skip that and ultimately return the raw code.
    expect(languageDisplayName("tlh")).toBe("tlh");
  });
});

describe("buildTranslationRequestUrl", () => {
  it("targets the repo issues/new with body, title and label", () => {
    const url = buildTranslationRequestUrl("el", "Greek");
    expect(url.startsWith("https://github.com/clintongormley/ha-fado/issues/new?")).toBe(true);
    const q = new URL(url).searchParams;
    expect(q.get("labels")).toBe("translation");
    expect(q.get("title")).toBe("Translation request: Greek (el)");
    expect(q.get("body")).toContain("Fado Light Fader");
    expect(q.get("body")).toContain("Greek (el)");
  });
  it("encodes region variants", () => {
    const q = new URL(buildTranslationRequestUrl("pt-BR", "Brazilian Portuguese")).searchParams;
    expect(q.get("title")).toBe("Translation request: Brazilian Portuguese (pt-BR)");
  });
});

describe("splitMessageParts", () => {
  it("splits a template into text and bold parts", () => {
    const parts = splitMessageParts("Hi {language}, try {product}!", {
      language: "Français",
      product: "Fado Light Fader",
    });
    expect(parts).toEqual([
      { text: "Hi " },
      { bold: "Français" },
      { text: ", try " },
      { bold: "Fado Light Fader" },
      { text: "!" },
    ]);
  });
  it("keeps an unknown placeholder as literal text", () => {
    expect(splitMessageParts("a {x} b", {})).toEqual([{ text: "a {x} b" }]);
  });
});

describe("dismissal set", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips a single dismissal", () => {
    expect(isLangRequestDismissed("fr")).toBe(false);
    persistDismissedLangRequest("fr");
    expect(isLangRequestDismissed("fr")).toBe(true);
  });
  it("remembers earlier dismissals when a new one is added (it's a set)", () => {
    persistDismissedLangRequest("fr");
    persistDismissedLangRequest("de");
    expect(isLangRequestDismissed("fr")).toBe(true);
    expect(isLangRequestDismissed("de")).toBe(true);
  });
  it("de-dups", () => {
    persistDismissedLangRequest("fr");
    persistDismissedLangRequest("fr");
    expect(readDismissedLangRequests()).toEqual(["fr"]);
  });
  it("returns [] on malformed storage", () => {
    localStorage.setItem(LANG_DISMISSED_KEY, "not json");
    expect(readDismissedLangRequests()).toEqual([]);
  });
});
```

Add `import { beforeEach } from "vitest";` to the test file's vitest import.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- fado-logic`
Expected: FAIL — helpers not exported.

- [ ] **Step 3: Implement** — append to `custom_components/fado/frontend/fado-logic.js`

```js
// ── Banner helpers ───────────────────────────────────────────

/** Native display name for a language code; native -> English -> raw code. */
export function languageDisplayName(code) {
  if (!code) return code;
  const tryName = (locale) => {
    try {
      const name = new Intl.DisplayNames([locale], { type: "language" }).of(code);
      // Intl defaults to fallback:"code", so an unknown tag echoes `code` back.
      return name && name !== code ? name : null;
    } catch {
      return null;
    }
  };
  return tryName(code) || tryName("en") || code;
}

const REPO = "clintongormley/ha-fado";

/** Prefilled GitHub "new issue" URL (uses ?body=, not ?template=). */
export function buildTranslationRequestUrl(code, displayName) {
  const body =
    `I'd like Fado Light Fader to be translated into: ${displayName} (${code})\n\n` +
    `- [ ] I'm happy to review the translations\n`;
  const params = new URLSearchParams({
    labels: "translation",
    title: `Translation request: ${displayName} (${code})`,
    body,
  });
  return `https://github.com/${REPO}/issues/new?${params.toString()}`;
}

/**
 * Split a message template into text/bold parts. `boldValues` maps placeholder
 * names to the value rendered bold; unknown placeholders stay literal text.
 * Adjacent text parts are merged.
 */
export function splitMessageParts(template, boldValues) {
  const parts = [];
  const pushText = (t) => {
    if (!t) return;
    const last = parts[parts.length - 1];
    if (last && "text" in last) last.text += t;
    else parts.push({ text: t });
  };
  const re = /\{(\w+)\}/g;
  let last = 0;
  let m;
  while ((m = re.exec(template))) {
    pushText(template.slice(last, m.index));
    if (Object.prototype.hasOwnProperty.call(boldValues, m[1])) {
      parts.push({ bold: boldValues[m[1]] });
    } else {
      pushText(m[0]);
    }
    last = re.lastIndex;
  }
  pushText(template.slice(last));
  return parts;
}

// ── Dismissal (a SET, so earlier dismissals are never forgotten) ──

export const LANG_DISMISSED_KEY = "fado_lang_request_dismissed";

export function readDismissedLangRequests() {
  try {
    const raw = JSON.parse(localStorage.getItem(LANG_DISMISSED_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

export function isLangRequestDismissed(code) {
  return readDismissedLangRequests().includes(code);
}

export function persistDismissedLangRequest(code) {
  try {
    const set = new Set(readDismissedLangRequests());
    set.add(code);
    localStorage.setItem(LANG_DISMISSED_KEY, JSON.stringify([...set]));
  } catch {
    // storage unavailable — ignore
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- fado-logic`
Expected: PASS (display name incl. echo-code case, URL, split, dismissal set).

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/fado-logic.js tests/frontend/fado-logic.test.js
git commit -m "feat(frontend): banner helpers (display name, deep-link, message split, dismissal set)"
```

---

## Task 6: Banner element + placement (`fado-lang-banner.js`, `fado-common.js`)

**Files:**
- Create (replace placeholder): `custom_components/fado/frontend/fado-lang-banner.js`
- Modify: `custom_components/fado/frontend/fado-common.js`

**Interfaces:**
- Consumes: `getLanguageSupport`, `languageDisplayName`, `buildTranslationRequestUrl`, `splitMessageParts`, `isLangRequestDismissed`, `persistDismissedLangRequest` (Tasks 4–5); `defaultLocalize` (Task 1).
- Produces: registered custom element `fado-lang-banner` with properties `.hass` and `.localize`.

- [ ] **Step 1: Implement the element** — `custom_components/fado/frontend/fado-lang-banner.js` (overwrite the placeholder)

```js
/**
 * Translation-request banner. Shown only when the user's HA language is not
 * covered (intersection of backend + frontend catalogs) and hasn't been
 * dismissed for that locale. Its audience always lacks a catalog for their
 * language, so the copy renders in the English fallback — expected.
 *
 * lit-element 2.4.0 has no willUpdate; state is resolved in update() before
 * super.update(), off the per-render path.
 */
import {
  LitElement,
  html,
  css,
} from "https://unpkg.com/lit-element@2.4.0/lit-element.js?module";

import {
  getLanguageSupport,
  languageDisplayName,
  buildTranslationRequestUrl,
  splitMessageParts,
  isLangRequestDismissed,
  persistDismissedLangRequest,
} from "./fado-logic.js";

import { defaultLocalize } from "./fado-i18n.js";

const PRODUCT = "Fado Light Fader";

class FadoLangBanner extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      localize: { attribute: false },
    };
  }

  constructor() {
    super();
    this.localize = defaultLocalize;
    this._view = null;
    this._dismissedCode = null;
  }

  update(changedProperties) {
    if (changedProperties.has("hass")) this._resolve();
    super.update(changedProperties);
  }

  _resolve() {
    const { available, code } = getLanguageSupport(this.hass);
    if (
      available ||
      !code ||
      this._dismissedCode === code ||
      isLangRequestDismissed(code)
    ) {
      this._view = null;
      return;
    }
    const displayName = languageDisplayName(code);
    this._view = {
      code,
      displayName,
      url: buildTranslationRequestUrl(code, displayName),
    };
  }

  _dismiss(e) {
    e.stopPropagation();
    if (!this._view) return;
    this._dismissedCode = this._view.code;
    persistDismissedLangRequest(this._view.code);
    this._view = null;
    this.requestUpdate();
  }

  render() {
    if (!this._view) return html``;
    const { displayName, url } = this._view;
    const parts = splitMessageParts(this.localize("language_request.message"), {
      language: displayName,
      product: PRODUCT,
    });
    return html`
      <div class="banner" role="status">
        <span class="globe" aria-hidden="true">🌐</span>
        <span class="msg">
          ${parts.map((p) =>
            "bold" in p ? html`<strong>${p.bold}</strong>` : p.text,
          )}
        </span>
        <a class="action" href=${url} target="_blank" rel="noopener noreferrer">
          ${this.localize("language_request.action")}
        </a>
        <ha-icon-button
          class="dismiss"
          .label=${this.localize("language_request.dismiss")}
          @click=${this._dismiss}
        >
          <ha-icon icon="mdi:close"></ha-icon>
        </ha-icon-button>
      </div>
    `;
  }

  static get styles() {
    return css`
      .banner {
        display: flex;
        align-items: center;
        gap: var(--fado-space-3, 12px);
        padding: var(--fado-space-2, 8px) var(--fado-space-4, 16px);
        margin-bottom: var(--fado-space-4, 16px);
        border: 1px solid var(--fado-border, var(--divider-color));
        border-left: 4px solid var(--fado-accent, var(--primary-color, #03a9f4));
        border-radius: var(--fado-radius, 8px);
        background: var(
          --fado-surface-2,
          var(--secondary-background-color, rgba(0, 0, 0, 0.05))
        );
        color: var(--fado-text, var(--primary-text-color));
        font-size: var(--fado-font-md, 14px);
      }
      .globe {
        font-size: 18px;
        line-height: 1;
      }
      .msg {
        flex: 1;
      }
      .action {
        color: var(--fado-accent, var(--primary-color, #03a9f4));
        font-weight: 500;
        text-decoration: none;
        white-space: nowrap;
      }
      .action:hover {
        text-decoration: underline;
      }
      .dismiss {
        color: var(--fado-text-muted, var(--secondary-text-color));
        --mdc-icon-button-size: 36px;
        --mdc-icon-size: 18px;
      }
    `;
  }
}

if (!customElements.get("fado-lang-banner")) {
  customElements.define("fado-lang-banner", FadoLangBanner);
}
```

- [ ] **Step 2: Import + render the banner** — `custom_components/fado/frontend/fado-common.js`

Add the side-effect import below the i18n import (top of file):

```js
import "./fado-lang-banner.js";
```

In `_renderContent`, the **final** return (the populated main-content branch) — add the banner above the header:

```js
      return html`
        <fado-lang-banner
          class="lang-banner"
          .hass=${this.hass}
          .localize=${(k, p) => this._t(k, p)}
        ></fado-lang-banner>
        ${this._renderHeader()}
        ${this._compact ? this._renderCardView() : this._renderTableView()}
      `;
```

(Leave the loading / auth-error / no-data / empty branches unchanged — the banner is main-content-only.)

- [ ] **Step 3: Run the full suite**

Run: `npm test`
Expected: PASS (source-key-coverage now reads the real banner file and finds `language_request.*` keys in EN).

- [ ] **Step 4: Manual verification (recommended)**

Deploy (`cp to ha`) and hard-refresh. With HA language set to an unsupported one (e.g. Greek), confirm: banner shows above the header; **Request a translation →** opens a prefilled GitHub issue (title/body/label) in a new tab; ✕ dismisses and it stays gone after reload; switching HA to French shows no banner. (See §Verification.)

- [ ] **Step 5: Commit**

```bash
git add custom_components/fado/frontend/fado-lang-banner.js custom_components/fado/frontend/fado-common.js
git commit -m "feat(frontend): translation-request banner element + placement"
```

---

## Task 7: Issue template, docs, changelog

**Files:**
- Create: `.github/ISSUE_TEMPLATE/translation_request.md`
- Modify: `docs/developers/design-system.md`
- Modify: `CHANGES.md`

- [ ] **Step 1: Create the issue template** — `.github/ISSUE_TEMPLATE/translation_request.md`

```markdown
---
name: Translation request
about: Ask for Fado Light Fader to be translated into your language
title: 'Translation request: '
labels: translation
---

I'd like Fado Light Fader to be translated into:

<!-- e.g. Greek (el) -->

- [ ] I'm happy to review the translations
```

- [ ] **Step 2: Document the i18n layer + banner** — append a section to `docs/developers/design-system.md`

```markdown
---

## 7. Frontend i18n and the translation-request banner

### Catalogs

- English is embedded in `fado-i18n.js` as `EN` — the source of truth and the
  synchronous fallback (no fetch, no flash).
- Other languages live as `frontend/translations/<lang>.json`, fetched on demand
  by `loadCatalog(code)` (exact code, then the base before `-`). They are
  **AI-generated, pending native review**.
- `localize(catalog, fallback, key, params)` does a dotted-key lookup
  (catalog → fallback → raw key) and interpolates `{param}` placeholders.

### Using it in the mixin

`FadoCoreMixin` exposes `this._t(key, params)` and loads the active language's
catalog into the reactive `_catalog` state via `_maybeLoadCatalog()` (called
from `connectedCallback` and `updated()` — lit-element 2.4.0 has no
`willUpdate`). Any new UI string must be added to `EN` and rendered via
`this._t("…")`. A test (`tests/frontend/fado-i18n.test.js`) scans the source for
`_t("…")` keys and fails if one is missing from `EN`.

### Language coverage

`getLanguageSupport(hass)` returns `{ available, code, baseCode }`. A language is
"available" only if it is in **both** `BACKEND_LANGUAGES` and
`FRONTEND_LANGUAGES` (exact-then-base) — the two arrays are guarded by tests
against their folders so they can't drift.

### Banner

`<fado-lang-banner>` (`fado-lang-banner.js`) renders at the top of the populated
main-content branch when the user's language is not covered and hasn't been
dismissed for that locale. Dismissals are stored as a **set** under
`fado_lang_request_dismissed`. The action link is a prefilled GitHub issue built
by `buildTranslationRequestUrl` using `?body=` (so it prefills before any
template PR is merged). The copy always renders in English (its audience has no
catalog for their language — expected).
```

- [ ] **Step 3: Update the logic-module list in `docs/developers/design-system.md`**

In section 5's bullet list, add entries for `getLanguageSupport`, `BACKEND_LANGUAGES`/`FRONTEND_LANGUAGES`, `languageDisplayName`, `buildTranslationRequestUrl`, `splitMessageParts`, and the dismissal helpers; note that `needsSetupLabel(count, t)` now takes a localizer.

- [ ] **Step 4: Add changelog entries** — `CHANGES.md` under `## [Unreleased]`

```markdown
### Added
- Frontend internationalisation: the Fado panel/card UI now loads per-language
  catalogs (`frontend/translations/<lang>.json`); English is the built-in
  fallback. Non-English UI translations are AI-generated and pending native
  review — corrections welcome.
- A dismissable banner that nudges users whose Home Assistant language Fado does
  not yet support to request a translation via a prefilled GitHub issue.

### Changed
- Panel/card UI strings are now localised via the new i18n layer (English output
  unchanged).
```

- [ ] **Step 5: Verify nothing broke + commit**

Run: `npm test`
Expected: PASS.

```bash
git add .github/ISSUE_TEMPLATE/translation_request.md docs/developers/design-system.md CHANGES.md
git commit -m "docs: i18n + translation-request banner (template, design-system, changelog)"
```

---

## Verification (before opening the PR)

- [ ] `npm test` — all suites green; check coverage on new files (`fado-i18n.js`, the new `fado-logic.js` exports) is >90%.
- [ ] `ruff check . && ruff format .` — no Python changed, but run to satisfy the repo gate.
- [ ] Live panel (`cp to ha`, hard refresh): English unchanged; pick a covered non-English language (e.g. `de`) and confirm the panel renders in that language and **no** banner; pick an unsupported language (e.g. `el`) and confirm the banner appears, the action opens a correctly-prefilled issue, ✕ dismisses and persists, and switching to another unsupported language (e.g. `th`) re-prompts while the dismissed one stays hidden.
- [ ] Confirm merge-method preference with the maintainer (no squash?) before merging.

## Self-Review (completed during planning)

- **Spec coverage:** i18n layer (Tasks 1–2), auto-translations (Task 3), detection/intersection + guards (Task 4), helpers incl. display-name echo-guard + URL `?body=` + dismissal set (Task 5), banner element + placement (Task 6), issue template + docs + changelog (Task 7). Every spec section maps to a task.
- **Adaptations recorded:** no `willUpdate` (lit-element 2.4.0) → `update()`/`updated()`; no bundle rebuild (no-build frontend); no backend-catalog keys (check_translations); `translation` label already exists; no `.layout`/flex catch-all so no `flex:0 0 auto` fix.
- **Type/name consistency:** `_t`, `_catalog`, `_maybeLoadCatalog`, `EN`, `localize`, `loadCatalog`, `getLanguageSupport`, `BACKEND_LANGUAGES`, `FRONTEND_LANGUAGES`, `languageDisplayName`, `buildTranslationRequestUrl`, `splitMessageParts`, `LANG_DISMISSED_KEY`, `readDismissedLangRequests`, `isLangRequestDismissed`, `persistDismissedLangRequest`, `needsSetupLabel(count, t)` — used consistently across tasks.
- **Placeholder scan:** every code/test step contains full code; the only "placeholder" file is the intentional `fado-lang-banner.js` stub in Task 2 Step 7, replaced in Task 6 Step 1.
```
