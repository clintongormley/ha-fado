# Frontend i18n + translation-request banner — design

Date: 2026-06-28
Status: approved (pending written-spec review)
Branch: `feat/frontend-i18n-translation-banner`

## 1. Goal

Two bundled outcomes for the Fado frontend (sidebar panel + Lovelace card, which
share `fado-common.js`):

1. **Frontend i18n.** Introduce a real localisation layer for the panel UI, which
   is currently hardcoded English, and ship UI catalogs for the same set of
   languages the integration already translates on the backend. Non-English
   catalogs are **AI-generated, pending native review**.
2. **Translation-request banner.** A dismissable banner at the top of the panel's
   main content that nudges users whose Home Assistant language Fado does **not**
   ship to request a translation via a prefilled GitHub issue.

   > 🌐 Your Home Assistant language is **Français**, but **Fado Light Fader**
   > isn't available in it yet. **[Request a translation →]** ✕

Dismissal persists per-locale: the same language never re-nags; a different
uncovered language re-prompts. Region/script variants (pt-BR, zh-Hant) are
first-class.

## 2. Context (what this repo actually is)

- **No frontend i18n today.** `custom_components/fado/frontend/fado-common.js` is
  the shared source for both the panel and the card; all UI strings are hardcoded
  English. There is no `localize`.
- **No build step.** `fado-common.js` is the served source; `panel.js` /
  `fado-card.js` import it; Lit is loaded from a CDN. There is no
  bundle/transpile/minify, so "rebuild & grep the bundle" does **not** apply.
- **Two catalog sets after this work:**
  - *Backend* `custom_components/fado/translations/*.json` (25 languages):
    config-flow / entity / service strings, validated against `strings.json` by
    `scripts/check_translations.py`. The pre-push hook runs it `--strict` (every
    language must translate every key). **Untouched by this work** — we add **no**
    keys here (doing so would break CI and create dead keys the frontend never
    reads).
  - *Frontend* `custom_components/fado/frontend/translations/*.json` (new): the
    panel UI catalogs. Fully separate from the backend set and from
    `check_translations.py`, so it never gates a release.
- **Pure logic → `fado-logic.js`** with a vitest test
  (`tests/frontend/*.test.js`, happy-dom). The CDN Lit cannot be imported in the
  test runner, so **Lit element rendering is not unit-tested** in this repo; the
  testable behaviour lives in pure functions.
- **Conventions:** `--fado-*` design tokens with `var(--token, real-fallback)`;
  `localStorage` keys prefixed `fado_`, JSON, try/catch (e.g.
  `_loadCollapsedState`); `ha-icon-button` is eagerly registered (use directly).
- **GitHub:** repo `clintongormley/ha-fado`; product name **"Fado Light Fader"**;
  the `translation` label **already exists**; `blank_issues_enabled: true` (so
  `?body=` deep-links work); existing issue templates are `.yml` forms.
- **Static mount:** the integration registers `/fado_panel` → the `frontend/`
  directory. New files under `frontend/` (incl. `frontend/translations/`) are
  served automatically.

## 3. Decisions (from brainstorming)

- **Scope:** bundle frontend i18n + auto-translations + the banner in one branch
  (staged commits).
- **Coverage / "translated":** a language counts as covered only if it has **both**
  a backend translation **and** a frontend UI catalog (**intersection**). Because
  the frontend catalogs are generated for the same 25 languages as the backend,
  the intersection is those 25, and the banner fires only for genuinely
  unsupported languages (e.g. Greek, Thai).
- **Variant semantics:** exact-then-base, mirroring how HA loads strings. `pt`
  covers pt-BR/pt-PT; `en` covers en-GB; `zh-Hans` covers only zh-Hans (zh-Hant
  still gets the banner). Undeterminable language → no banner.
- **Auto-translations:** I generate the 24 non-English UI catalogs (English is the
  embedded source/fallback). They are AI-generated and flagged for review; the
  banner's "happy to review" checkbox also solicits review of these.
- **Issue template:** `.md` with front-matter (per the original spec).
- **Placement:** top of the main content branch only (above the header);
  admin-only in practice (non-admins hit the auth-error branch).
- **Catalog mechanism:** per-language JSON files + an embedded English fallback
  (no fetch flash for English; non-English fetched on demand).

## 4. Architecture

### 4.1 i18n layer — `fado-i18n.js` (new)

- **Embedded English** (`EN`, a JS object) is the synchronous source of truth and
  fallback. The panel renders correct English instantly; there is no loading
  state and no flash.
- **`localize(catalog, fallback, key, params)` — pure.** Dotted-key lookup in
  `catalog`, then `fallback` (English), then the raw key. Interpolates `{param}`
  placeholders. Unit-tested.
- **`loadCatalog(code)` — impure/thin.** Resolves exact→base (e.g. `pt-BR` →
  `pt-BR.json` → `pt.json` → none), fetches relative to `import.meta.url`
  (`./translations/<code>.json`), (no internal cache — the mixin's `_catalogLang` guard avoids re-fetching the same language), swallows fetch errors
  (returns `null` → English fallback). Not unit-tested (IO; matches repo
  convention).
- **Mixin wiring (`fado-common.js`):** in `willUpdate(changed.has("hass"))`,
  derive the active language and, if it differs from the loaded one, call
  `loadCatalog` and cache the result in `@state _catalog` (triggering a
  re-render). `this._t(key, params)` = `localize(this._catalog, EN, key, params)`.

### 4.2 Panel string conversion (`fado-common.js`, `fado-logic.js`)

Behaviour-preserving: every hardcoded English UI string becomes `this._t("key")`
(or, for the pure `needsSetupLabel`, an injected localizer). English output stays
byte-identical. Strings to convert (~30), grouped:

- Header / actions: `Fado Light Fader`, `Loading...`, `Autoconfigure`,
  `Autoconfigure ({count})`, `Configuring {count} light(s)... ({done}/{total})`.
- States: `Administrator access is required to configure Fado.`,
  `No lights found.`, `No active lights available`, `No lights in this area`.
- Table headers: `Min Delay (ms)`, `Min Brightness`, `Native Transitions`,
  `Exclude`.
- Settings: `Global min delay:`, `The absolute minimum delay for all lights`,
  `Download diagnostics`.
- Card view: `Exclude`, `Configure`, `Entity`, `Min delay`, `Min brightness`,
  `Native transitions`.
- Status: `● Needs setup`, the `needsSetupLabel` one/other pair
  (`1 needs setup` / `{count} need setup`).
- Native-transition options: `Yes`, `No`, `Disable`; the `ms` suffix.

Pluralisation keeps the existing one/other branching (separate keys), not full
ICU plural rules. For languages with richer plural systems the two-form rendering
is an approximation, acceptable for an AI-generated v1 flagged for review.

A **source-key-coverage test** scans `fado-common.js` (and `fado-logic.js`) for
`_t("…")` / localizer keys and asserts each exists in `EN`, failing CI on a
missing key.

### 4.3 Frontend catalogs — `frontend/translations/<lang>.json` (new)

- 24 files for `bg, cs, da, de, es, fi, fr, hu, id, it, ja, ko, nb, nl, pl, pt,
  ro, sk, sl, sv, tr, uk, vi, zh-Hans` (English is embedded, not a file).
- Generated via parallel translation subagents under strict rules: **preserve
  `{placeholders}` and keys exactly; valid JSON; mirror the English structure;
  translate values only.**
- Marked AI-generated/pending-review in CHANGES.md, the PR body, and the docs.

### 4.4 Detection (pure, `fado-logic.js`)

```
getLanguageSupport(hass) -> { available, code, baseCode }
  code      = hass.locale?.language ?? hass.language
  (undeterminable) -> { available: true, code: null, baseCode: null }   // no nudge
  baseCode  = code.split("-")[0]
  backend   = BACKEND_LANGUAGES.has(code)  || BACKEND_LANGUAGES.has(baseCode)
  frontend  = FRONTEND_LANGUAGES.has(code) || FRONTEND_LANGUAGES.has(baseCode)
  available = backend && frontend                                        // intersection
```

`BACKEND_LANGUAGES` and `FRONTEND_LANGUAGES` are explicit arrays in
`fado-logic.js`, each **guarded by a vitest test** that reads the corresponding
folder and asserts the array matches (so they can't silently drift). `en` is a
member of `FRONTEND_LANGUAGES` even though it has no file (embedded).

### 4.5 Helpers (pure, `fado-logic.js`)

- **`languageDisplayName(code)`** via `new Intl.DisplayNames([code], {type:
  "language"}).of(code)`; fallback native → English → raw code; every Intl call
  try/catch-guarded. Guard the native result with `if (native && native !== code)`
  (Intl defaults to `fallback:"code"`, so an unknown tag echoes the code back).
- **`buildTranslationRequestUrl(code, displayName)`** via `URLSearchParams`:
  `https://github.com/clintongormley/ha-fado/issues/new?labels=translation&title=Translation request: <displayName> (<code>)&body=<prefilled>`.
  Uses **`?body=`** (prefills immediately, pre-merge), **not** `?template=`.
- **Dismissal set** on key `fado_lang_request_dismissed` (JSON **array**):
  `isLangRequestDismissed(code)`, `persistDismissedLangRequest(code)`
  (append + de-dup); read returns `[]` on missing/malformed; all try/catch.
  (A single-value store would forget earlier dismissals — store a set.)

### 4.6 Banner element — `fado-lang-banner.js` (new)

- A `LitElement` registered from `fado-common.js`; rendered as `<fado-lang-banner
  .hass=${this.hass} class="lang-banner">` at the top of the main content branch.
- Resolves `{show, code, displayName, url}` in `willUpdate(changed.has("hass"))`
  (localStorage read + `Intl.DisplayNames` + URL build off the per-render path),
  caches in `@state`; keeps an in-memory `_dismissedCode` for instant hide; render
  reads the cache.
- `localize` property defaults to a no-op English localizer (`= defaultLocalize`),
  not a `!` assertion.
- ✕ = `ha-icon-button` (visible label → `aria-label`); dismiss handler calls
  `e.stopPropagation()` and `persistDismissedLangRequest(code)`.
- Action = native `<a target="_blank" rel="noopener noreferrer">`.
- Styled with `var(--fado-token, real-fallback)` (tokens inherit from the panel
  host through the shadow boundary). The `.layout`/flex catch-all gotcha does not
  exist in this repo, so no `flex:0 0 auto` fix is needed.

### 4.7 Repo additions

- `.github/ISSUE_TEMPLATE/translation_request.md`: front-matter
  (`name`, `about`, `title: 'Translation request: '`, `labels: translation`) +
  body with "I'd like Fado Light Fader to be translated into: …" and a
  `- [ ] I'm happy to review the translations` checkbox.
- Docs: extend `docs/developers/design-system.md` (i18n layer, the `_t` helper,
  the banner, the new files); add `CHANGES.md` entries under `## [Unreleased]`.

## 5. Testing (TDD)

Pure functions, exhaustive:

- **localize:** key hit; nested key; missing key → fallback → raw; `{param}`
  interpolation; missing param left as-is.
- **detection:** covered (both sides, exact); covered via base; uncovered because
  backend-only; uncovered because frontend-only; region covered via base
  (pt-BR→pt); script not covered (zh-Hant); en-GB via en; empty / undeterminable
  → no nudge.
- **display name:** native; native→English fallback; English→raw fallback;
  native-echoes-code case (tlh) skips to English/raw.
- **URL:** encoding incl. region variant; label + title + body present.
- **storage:** round-trip; multi-locale set membership; de-dup; `[]` on
  missing/malformed; graceful failure when storage throws.
- **coverage guards:** `BACKEND_LANGUAGES` == backend folder; `FRONTEND_LANGUAGES`
  == frontend folder ∪ {`en`}; every `_t` key used in source exists in `EN`.

Banner behaviours (shows when uncovered+undismissed; hidden when covered; hidden
when dismissed-for-this-locale; reappears for a different uncovered locale; stays
dismissed for an earlier locale after dismissing another; dismiss persists+hides;
correct href) are expressed through the pure detection/storage functions, which
are fully covered; the element is a thin renderer over them.

Target **>90%** coverage on new pure files. `npm test` is green throughout.

## 6. Out of scope / non-goals

- No changes to backend `translations/*.json` or `strings.json`.
- No full ICU plural-rule engine (one/other approximation).
- No `gh label create` (the `translation` label already exists).
- No bundle rebuild (no-build frontend).

## 7. Delivery

One branch, staged commits, in order:

1. i18n foundation (`fado-i18n.js`, `_t` wiring) + behaviour-preserving panel
   conversion + the source-key-coverage test.
2. Auto-generated `frontend/translations/*.json` (24 languages) + the
   folder-vs-array coverage tests.
3. Detection + helpers + `<fado-lang-banner>` + placement + tests.
4. Issue template, docs, CHANGES.md.

Merge method to be confirmed with the maintainer before merging (no squash?).
Verification of the live panel can happen in a Docker worktree at implementation
time if desired.
