"""Tests for scripts/extract_changelog.py.

The script extracts the body of a single ``## [<version>]`` section from a
Keep a Changelog file so the release workflow can publish it as the GitHub
Release notes. A missing or empty section exits non-zero so the workflow can
fall back to GitHub's auto-generated notes.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "extract_changelog.py"

SAMPLE = """\
# Changes

All notable user-facing changes to this integration are documented in this file.

## [Unreleased]

### Added

- Something pending that must never leak into a released section.

## [2.10.0] - 2026-07-01

### Added

- Tenth-minor feature; must not be confused with 2.1.0.

## [2.1.0] - 2026-06-21

### Added

- Frontend: responsive layout with collapsible per-light cards.

### Changed

- Frontend: themed select control and a --fado-* design-token layer.

## [2.1.0-rc.1] - 2026-06-18

### Added

- Release-candidate-only note that 2.1.0 must not pick up.

## [2.0.0] - 2026-06-14

### Added

- Older release body.

## [1.0.0]

### Added

- First public release (heading carries no date).

## [0.9.0] - 2026-05-01

### Fixed

- A bug.
"""


def _changelog(tmp_path: Path, text: str = SAMPLE) -> Path:
    path = tmp_path / "CHANGES.md"
    path.write_text(text, encoding="utf-8")
    return path


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_extracts_version_body(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "### Added" in out
    assert "responsive layout" in out
    assert "### Changed" in out
    assert "design-token layer" in out


def test_excludes_the_heading_line(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    assert "## [2.1.0]" not in result.stdout


def test_stops_at_next_heading(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    # Must not bleed into the adjacent (older) section.
    assert "Release-candidate-only note" not in result.stdout
    assert "Older release body" not in result.stdout


def test_never_matches_unreleased(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    assert "must never leak" not in result.stdout


def test_exact_match_not_prerelease(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    assert "Release-candidate-only" not in result.stdout


def test_exact_match_not_prefix_collision(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    assert "Tenth-minor feature" not in result.stdout


def test_prerelease_version_can_be_extracted(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.1.0-rc.1", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    assert "Release-candidate-only note" in result.stdout
    assert "responsive layout" not in result.stdout


def test_heading_without_date_matches(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("1.0.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    assert "First public release" in result.stdout
    assert "A bug" not in result.stdout  # stops before 0.9.0


def test_missing_version_exits_nonzero(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("9.9.9", "--changelog", str(cl))
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip() != ""


def test_empty_section_exits_nonzero(tmp_path: Path):
    cl = _changelog(
        tmp_path,
        text="# Changes\n\n## [3.0.0] - 2026-08-01\n\n## [2.0.0]\n\n### Added\n\n- x\n",
    )
    result = _run("3.0.0", "--changelog", str(cl))
    assert result.returncode != 0
    assert result.stdout == ""


def test_output_is_trimmed(tmp_path: Path):
    cl = _changelog(tmp_path)
    result = _run("2.0.0", "--changelog", str(cl))
    assert result.returncode == 0, result.stderr
    # Exactly the section body: no leading/trailing blank lines, one trailing newline.
    assert result.stdout == "### Added\n\n- Older release body.\n"
