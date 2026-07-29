#!/usr/bin/env bash
# Build the full ha-fado site: the interactive demo at the root, the
# mkdocs-material documentation under /docs/.
#
# Both tools empty their own output directory on build, so each builds into its
# own place and this script assembles the result — nesting one inside the other
# would let a rebuild erase the other half.
#
# This is the same build CI runs (.github/workflows/pages.yml), so a green run
# here means a green build there. Note CI additionally runs the frontend test
# suite first — `npm test` guards the demo's links against the docs pages they
# point at, and is not part of this script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_PATH="${PAGES_BASE_PATH:-/ha-fado/}"
DIST="$ROOT/dist"

echo "▶ Documentation (mkdocs --strict)"
(cd "$ROOT" && mkdocs build --strict)

echo "▶ Demo (base $BASE_PATH)"
(cd "$ROOT/demo" && PAGES_BASE_PATH="$BASE_PATH" npm run build:pages)

echo "▶ Assembling dist/"
rm -rf "$DIST"
mkdir -p "$DIST"
cp -R "$ROOT/demo/dist-pages/." "$DIST/"
cp -R "$ROOT/site" "$DIST/docs"
touch "$DIST/.nojekyll"

echo "▶ Smoke checks"
for f in index.html docs/index.html docs/actions/fade-lights/index.html; do
  if [ ! -s "$DIST/$f" ]; then
    echo "✗ missing or empty: dist/$f" >&2
    exit 1
  fi
done
if ! grep -q "${BASE_PATH}assets/" "$DIST/index.html"; then
  echo "✗ demo assets not built against base $BASE_PATH" >&2
  exit 1
fi

echo "✓ site built at $DIST"
