import { describe, it, expect, beforeEach } from "vitest";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
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
  getLanguageSupport,
  BACKEND_LANGUAGES,
  FRONTEND_LANGUAGES,
  languageDisplayName,
  buildTranslationRequestUrl,
  splitMessageParts,
  LANG_DISMISSED_KEY,
  readDismissedLangRequests,
  isLangRequestDismissed,
  persistDismissedLangRequest,
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

describe("languageDisplayName", () => {
  it("returns a native display name for a known language", () => {
    // fr in fr -> "français" (capitalisation varies by ICU; just assert non-code)
    const name = languageDisplayName("fr");
    expect(typeof name).toBe("string");
    expect(name).not.toBe("fr");
    expect(name.toLowerCase()).toContain("fran");
  });
  it("falls back to the raw code for an unknown tag (Intl echoes the code)", () => {
    // Intl.DisplayNames defaults to fallback:'code' so an unknown tag echoes back;
    // the guard must skip that and ultimately return the raw code.
    // Note: 'tlh' (Klingon) is known to ICU in Node 26 so we use 'xyz' instead,
    // which is a private-use subtag guaranteed to echo in all ICU builds.
    expect(languageDisplayName("xyz")).toBe("xyz");
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

describe("language coverage guards", () => {
  // Resolve via fileURLToPath (not the happy-dom URL global, which readdirSync
  // rejects with "URL must be of scheme file").
  const here = dirname(fileURLToPath(import.meta.url));
  const langs = (rel) =>
    readdirSync(join(here, rel))
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(/\.json$/, ""));

  it("BACKEND_LANGUAGES matches the backend translations folder", () => {
    expect([...BACKEND_LANGUAGES].sort()).toEqual(
      langs("../../custom_components/fado/translations").sort(),
    );
  });
  it("FRONTEND_LANGUAGES matches the frontend catalogs plus embedded en", () => {
    const files = langs("../../custom_components/fado/frontend/translations");
    expect([...FRONTEND_LANGUAGES].sort()).toEqual(["en", ...files].sort());
  });
});
