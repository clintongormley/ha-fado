#!/usr/bin/env python3
"""Extract one version's section body from a Keep a Changelog file.

Used by the release workflow to publish the curated ``CHANGES.md`` entry for the
released version as the GitHub Release notes, instead of GitHub's auto-generated
list of commit/PR titles.

Given a version, finds the heading whose bracketed name equals that version
*exactly* — ``## [2.1.0] - 2026-06-21`` matches ``2.1.0`` but not ``Unreleased``,
the prefix collision ``2.10.0``, or the pre-release ``2.1.0-rc.1`` — and prints
the body beneath it (up to the next ``## `` heading) with the heading line itself
removed and surrounding blank lines trimmed.

Usage: extract_changelog.py <version> [--changelog PATH]
       (PATH defaults to CHANGES.md at the repository root.)

Exit code: 0 and the section body on stdout when a non-empty section is found;
1 with a message on stderr (and nothing on stdout) when the section is missing
or empty, so the caller can fall back to auto-generated notes.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = REPO_ROOT / "CHANGES.md"

# A version heading: "## [<name>]" with an optional "- <date>" suffix. The
# bracketed name is captured so it can be compared to the requested version
# exactly (no prefix/substring matching).
HEADING_RE = re.compile(r"^##\s+\[([^\]]+)\]")


def extract(text: str, version: str) -> str | None:
    """Return the trimmed body of the ``## [version]`` section, or None.

    None means the section is absent or contains only whitespace.
    """
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and match.group(1) == version:
            start = i + 1
            break
    if start is None:
        return None

    body: list[str] = []
    for line in lines[start:]:
        if HEADING_RE.match(line):
            break
        body.append(line)

    section = "\n".join(body).strip("\n")
    return section if section.strip() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="version to extract, e.g. 2.1.0")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=DEFAULT_CHANGELOG,
        help="path to the changelog (default: CHANGES.md at the repo root)",
    )
    args = parser.parse_args(argv)

    try:
        text = args.changelog.read_text(encoding="utf-8")
    except OSError as err:
        print(f"error: cannot read {args.changelog}: {err}", file=sys.stderr)
        return 1

    section = extract(text, args.version)
    if section is None:
        print(
            f"error: no '## [{args.version}]' section found in {args.changelog}",
            file=sys.stderr,
        )
        return 1

    print(section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
