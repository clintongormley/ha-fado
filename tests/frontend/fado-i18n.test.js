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
