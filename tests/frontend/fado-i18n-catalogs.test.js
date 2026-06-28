import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { EN } from "../../custom_components/fado/frontend/fado-i18n.js";

// Resolve via fileURLToPath (not the happy-dom URL global, which readdirSync
// rejects with "URL must be of scheme file").
const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, "../../custom_components/fado/frontend/translations");

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
      const data = JSON.parse(readFileSync(join(dir, file), "utf8"));
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
