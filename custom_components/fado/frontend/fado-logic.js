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
