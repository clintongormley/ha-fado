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
  pruneCollapsedState,
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

describe("pruneCollapsedState", () => {
  const data = {
    areas: [
      { area_id: "kitchen", lights: [{ entity_id: "light.a" }, { entity_id: "light.b" }] },
      { area_id: null, lights: [{ entity_id: "light.c" }] },
    ],
  };

  it("keeps keys for current areas/lights and preserves their values", () => {
    const collapsed = {
      area_kitchen: false,
      area_none: true,
      "light_light.a": false,
      "light_light.b": true,
      "light_light.c": true,
    };
    expect(pruneCollapsedState(collapsed, data)).toEqual(collapsed);
  });

  it("drops stale area/light keys not present in the data", () => {
    const collapsed = {
      area_kitchen: true,
      area_bedroom: false, // removed area
      "light_light.a": false,
      "light_light.gone": true, // removed light
    };
    expect(pruneCollapsedState(collapsed, data)).toEqual({
      area_kitchen: true,
      "light_light.a": false,
    });
  });

  it("drops non-area/light cruft such as _version", () => {
    const collapsed = { _version: 3, area_kitchen: true, "light_light.a": true };
    expect(pruneCollapsedState(collapsed, data)).toEqual({
      area_kitchen: true,
      "light_light.a": true,
    });
  });

  it("returns an empty object when there is no data", () => {
    const collapsed = { area_kitchen: true, "light_light.a": false };
    expect(pruneCollapsedState(collapsed, null)).toEqual({});
    expect(pruneCollapsedState(collapsed, { areas: null })).toEqual({});
  });

  it("does not mutate the input object", () => {
    const collapsed = { area_kitchen: true, area_bedroom: false };
    const snapshot = { ...collapsed };
    pruneCollapsedState(collapsed, data);
    expect(collapsed).toEqual(snapshot);
  });
});
