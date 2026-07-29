import { existsSync, readFileSync, statSync } from "node:fs";
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

describe("vendored demo — attribution", () => {
  it("credits the original author on the page", () => {
    expect(PAGE).toContain("Interactive demo originally created by");
    expect(PAGE).toContain("Florian Horner");
    expect(PAGE).toContain("https://github.com/florianhorner/fado-light-fader-demo");
  });

  it("records provenance in UPSTREAM.md", () => {
    const upstream = readFileSync(join(ROOT, "demo/UPSTREAM.md"), "utf8");
    expect(upstream).toContain("77481986df105472976af02997f11b8c257c96ae");
    expect(upstream).toContain("BSD Zero Clause License");
  });

  it("keeps og.png small enough to ship", () => {
    const bytes = statSync(join(ROOT, "demo/public/og.png")).size;
    expect(bytes).toBeLessThan(800_000);
  });
});

describe("vendored demo — branding", () => {
  it("uses Fado's own brand icon, not a generic glyph", () => {
    // The brand icon ships inside the integration (custom_components/fado/brand/)
    // rather than being duplicated here, so there is one source of truth for it.
    expect(PAGE).toContain("brand/icon.png");
    expect(PAGE).not.toContain("Lightbulb");
  });

  it("imports a brand icon that actually exists", () => {
    // Asserting the import path alone would still pass if the icon were moved
    // or deleted — only the Vite build would notice, and only later.
    const ref = PAGE.match(/from "([^"]*brand\/icon\.png)"/)?.[1];
    expect(ref, "no brand icon import found in page.tsx").toBeDefined();
    const resolved = join(ROOT, "demo/app", ref);
    expect(existsSync(resolved), `${ref} → ${resolved}`).toBe(true);
  });

  it("names the project in full in the brand marks", () => {
    expect(PAGE).toContain("Fado Light Fader for Home Assistant");
    expect(PAGE).not.toContain("Fado demo");
  });
});
