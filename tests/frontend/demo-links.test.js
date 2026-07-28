import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Resolve via fileURLToPath (not the happy-dom URL global, which readFileSync
// rejects with "URL must be of scheme file").
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../../");
const PAGE = readFileSync(join(ROOT, "demo/app/page.tsx"), "utf8");
const INDEX = readFileSync(join(ROOT, "demo/github-pages/index.html"), "utf8");

const SITE = "https://clintongormley.github.io/ha-fado/";

describe("vendored demo — outbound links", () => {
  it("has no README deep links left", () => {
    const anchors = PAGE.match(/github\.com\/clintongormley\/ha-fado#[\w-]+/g) ?? [];
    expect(anchors).toEqual([]);
  });

  it("links to docs pages that exist, via BASE_URL", () => {
    const refs = [...PAGE.matchAll(/BASE_URL\}docs\/([\w./-]*)/g)].map((m) => m[1]);
    expect(refs.length).toBeGreaterThan(0);

    for (const ref of refs) {
      const rel = ref.replace(/\/$/, "");
      const candidates = rel === ""
        ? ["docs/index.md"]
        : [`docs/${rel}.md`, `docs/${rel}/index.md`];
      const found = candidates.some((c) => existsSync(join(ROOT, c)));
      expect(found, `${ref} → none of ${candidates.join(", ")}`).toBe(true);
    }
  });
});

describe("vendored demo — page metadata", () => {
  it("points canonical at the ha-fado site", () => {
    const canonical = INDEX.match(/rel="canonical"\s+href="([^"]+)"/)?.[1];
    expect(canonical).toBe(SITE);
  });

  it("points og:url and the social images at the ha-fado site", () => {
    const ogUrl = INDEX.match(/property="og:url"\s+content="([^"]+)"/)?.[1];
    expect(ogUrl).toBe(SITE);

    const images = [...INDEX.matchAll(/(?:property="og:image"|name="twitter:image")\s+content="([^"]+)"/g)]
      .map((m) => m[1]);
    expect(images.length).toBe(2);
    for (const image of images) {
      expect(image).toBe(`${SITE}og.png`);
    }
  });

  it("no longer advertises the upstream pages origin", () => {
    expect(INDEX).not.toContain("florianhorner.github.io");
  });
});
