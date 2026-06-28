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

/** Roll-up label for an area header; "" when none need setup. `t` is a localizer. */
export function needsSetupLabel(count, t) {
  if (!count) return "";
  return count === 1
    ? t("status.needs_setup_one", { count })
    : t("status.needs_setup_other", { count });
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

/**
 * Drop persisted collapse keys for areas/lights that no longer exist (and any
 * non-area/light cruft such as `_version`), preserving the stored value of the
 * keys that remain. Returns a new object; the caller seeds defaults for any
 * still-missing current keys. Prevents the `fado_collapsed` blob from growing
 * unboundedly as lights/areas churn.
 */
export function pruneCollapsedState(collapsed, data) {
  const valid = new Set();
  if (data && data.areas) {
    for (const area of data.areas) {
      valid.add(collapseKeyForArea(area));
      for (const light of area.lights) {
        valid.add(collapseKeyForLight(light.entity_id));
      }
    }
  }
  const pruned = {};
  for (const key of Object.keys(collapsed)) {
    if (valid.has(key)) pruned[key] = collapsed[key];
  }
  return pruned;
}

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
