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
