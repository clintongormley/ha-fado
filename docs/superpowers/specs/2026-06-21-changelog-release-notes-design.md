# Changelog-sourced GitHub Release notes

## Problem

The release workflow publishes GitHub Releases with
`generate_release_notes: true`, so the notes are GitHub's auto-generated list of
merged PR/commit titles. That duplicates raw commit chatter and ignores the
curated, user-facing `CHANGES.md` we already maintain per
[Keep a Changelog](https://keepachangelog.com/). The published notes should be
the changelog section for the released version.

## Decisions

- **Changelog promotion stays manual.** The maintainer edits `CHANGES.md` to
  rename `## [Unreleased]` → `## [<version>] - <date>` (and start a fresh empty
  `## [Unreleased]`) before tagging. `bin/release.sh` is **not** changed to do
  this automatically.
- **Missing section falls back to auto-notes.** If the tagged version has no
  matching `## [<version>]` section (e.g. a pre-release like `2.1.0-rc.1`, or a
  forgotten promotion), the workflow falls back to
  `generate_release_notes: true` — today's behaviour — so a release never gets
  blocked or published empty.
- **No runtime check in `bin/release.sh`.** Only its header comment gains a
  reminder. The workflow fallback is the safety net.

## Components

### `scripts/extract_changelog.py` (new)

Python helper, matching the existing `scripts/check_*.py` convention (Python
parses markdown sections far more reliably than bash/awk).

- Usage: `python3 scripts/extract_changelog.py <version> [--changelog PATH]`
  (default `CHANGES.md` resolved relative to the repo root).
- Matches the heading whose **bracket content equals `<version>` exactly**:
  `## [2.1.0] - 2026-06-21` matches `2.1.0`; it must **not** match `Unreleased`,
  the prefix collision `2.10.0`, or the pre-release `2.1.0-rc.1`. An optional
  `- <date>` suffix after the bracket is allowed and ignored.
- Prints the section **body** — everything after the heading line up to the next
  `## ` heading (the next older version) — with the `## [version]` line itself
  removed and surrounding blank lines trimmed. The `### Added` / `### Changed`
  sub-blocks are preserved.
- Exit `0` and print the body to stdout when a non-empty section is found.
- Exit non-zero, print nothing to stdout, and write a short message to stderr
  when the section is absent or contains only whitespace.

### `tests/test_extract_changelog.py` (new)

Subprocess-style tests mirroring `tests/test_release_script.py`. Cases:

- extracts a known version's body;
- the `## [version]` heading line is excluded from output;
- output stops at the next `## ` heading (no bleed into the older version);
- `Unreleased` is never matched;
- exact-match guards: `2.1.0` ≠ `2.1.0-rc.1`, `2.1.0` ≠ `2.10.0`;
- an optional `- <date>` suffix on the heading still matches;
- a missing version exits non-zero with empty stdout;
- a present-but-empty section exits non-zero.

### `.github/workflows/release.yml` (changed, *publish* job)

Add an extraction step before "Create GitHub Release" and make the body source
conditional:

```yaml
- name: Extract release notes from CHANGES.md
  id: notes
  env: { VERSION: ${{ steps.version.outputs.version }} }
  run: |
    if python3 scripts/extract_changelog.py "$VERSION" > release-notes.md; then
      echo "found=true" >> "$GITHUB_OUTPUT"
    else
      echo "found=false" >> "$GITHUB_OUTPUT"
    fi

- name: Create GitHub Release
  uses: softprops/action-gh-release@v3
  with:
    body_path: ${{ steps.notes.outputs.found == 'true' && 'release-notes.md' || '' }}
    generate_release_notes: ${{ steps.notes.outputs.found != 'true' }}
    prerelease: ${{ steps.version.outputs.prerelease }}
    make_latest: ${{ steps.version.outputs.prerelease == 'true' && 'false' || 'true' }}
```

Single step, mutually-exclusive inputs: found → use the file, no auto-notes;
not found → empty `body_path` (action-gh-release treats `''` as unset) plus
auto-notes. `prerelease` / `make_latest` are unchanged.

### Doc comments (changed)

`release.yml` header and `bin/release.sh` header gain a one-line reminder:
promote `## [Unreleased]` → `## [<version>] - <date>` in `CHANGES.md` before
tagging, or the release falls back to auto-generated notes.

## Out of scope

- Auto-promotion of the Unreleased section.
- Any hard pre-flight failure when the section is missing.
- Changes to the integration's runtime behaviour (no `CHANGES.md` entry; this is
  release tooling only).
