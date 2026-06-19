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
