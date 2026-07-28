# Vendored demo — provenance

This directory is a vendored copy of the Fado interactive demo.

| | |
| --- | --- |
| Upstream | <https://github.com/florianhorner/fado-light-fader-demo> |
| Author | Florian Horner |
| Vendored at | `77481986df105472976af02997f11b8c257c96ae` (2026-07-28) |
| Licence | BSD Zero Clause License (0BSD) — see `LICENSE.upstream` |

Included in Fado's documentation with the author's permission. 0BSD permits
use, modification and redistribution without attribution; the credit on the
page and in this file is offered rather than required.

## What was copied

Only the static Vite build surface: `app/`, `github-pages/`, `public/`,
`vite.pages.config.ts`, `postcss.config.mjs`, `tsconfig.json`. Upstream paths
are preserved so a re-sync is a plain diff.

Not copied: `worker/`, `db/`, `drizzle/`, `examples/`, `.openai/`, `build/`,
`tests/`, `next.config.ts`, `eslint.config.mjs`, `app/layout.tsx`,
`app/chatgpt-auth.ts`. None participate in `vite build --config
vite.pages.config.ts`, whose entry chain is `github-pages/index.html` →
`main.tsx` → `app/page.tsx`.

## What we changed

1. `package.json` trimmed from 20 dependencies to 11 (dropped `next`,
   `drizzle-*`, `@cloudflare/vite-plugin`, `@vitejs/plugin-rsc`,
   `react-server-dom-webpack`, `vinext`, `wrangler`, `eslint*`); `dev` replaced
   by `dev:pages`.
2. `tsconfig.json` stripped of the `next` TS plugin and `.next` type includes.
3. `app/page.tsx` — the README deep link and a new header Docs link point at the
   Fado docs site via `import.meta.env.BASE_URL`; the footer paragraph was
   reworded to credit Florian Horner as the demo's original author (with a
   link to his GitHub profile and to the upstream repo, noting the 0BSD
   licence) instead of the old "Unofficial community demo" / no-affiliation
   disclaimer, which no longer applied once the demo became Fado's own
   landing page.
4. `github-pages/index.html` — `canonical`, `og:url` and the social images point
   at <https://clintongormley.github.io/ha-fado/>; "unofficial" dropped from the
   descriptions.
5. `public/og.png` shrunk from 2,194,672 bytes (1731×909) to 501,908 bytes
   (1200×630). Losslessly: resized to the canonical Open Graph size of
   1200×630 with `sips` (near-identical aspect ratio, no distortion) and run
   through `oxipng -o max --zopfli --strip safe`, reaching a floor of 947,079
   bytes — still over the 800 KB budget, with no alpha channel or metadata
   left to strip. Quantized to a 256-colour palette with Floyd–Steinberg
   dithering (Pillow `Image.quantize(colors=256, method=MEDIANCUT,
   dither=FLOYDSTEINBERG)`) to avoid banding in the hero's orange/teal
   gradients, then re-ran `oxipng -o max --zopfli --strip safe` on the
   quantized file, landing at 501,908 bytes. Verified against the lossless
   1200×630 version with `PIL.ImageChops.difference`: mean per-channel diff
   ≈1.3/255, max ≈71/255, confined to gradient dithering noise — no visible
   banding on inspection. `github-pages/index.html` declares no
   `og:image:width`/`height`, so no metadata changes were needed.

## Re-syncing with upstream

```bash
git clone https://github.com/florianhorner/fado-light-fader-demo.git /tmp/fado-demo
git -C /tmp/fado-demo diff 77481986df105472976af02997f11b8c257c96ae..main -- app github-pages public vite.pages.config.ts postcss.config.mjs
```

Apply the relevant hunks by hand, keeping the five changes above intact, then
update the "Vendored at" SHA here and the SHA asserted in
`tests/frontend/demo-links.test.js`. Run `npm test` and
`scripts/build_site.sh` before committing.
