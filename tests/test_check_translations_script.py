"""Tests for scripts/check_translations.py, focusing on --strict mode.

The default behaviour treats a missing (untranslated) key as a warning and a
stale key (present in a translation but not in strings.json) as an error.
--strict additionally promotes missing keys to errors, so an incomplete
translation set fails the check — used by the pre-push hook to stop a new
string reaching a release untranslated.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_translations.py"


def _make_component(tmp_path: Path, strings: dict, translations: dict[str, dict]) -> Path:
    """Build a throwaway custom_components/<name>/ with strings + translations."""
    comp = tmp_path / "custom_components" / "demo"
    (comp / "translations").mkdir(parents=True)
    (comp / "strings.json").write_text(json.dumps(strings), encoding="utf-8")
    for lang, data in translations.items():
        (comp / "translations" / f"{lang}.json").write_text(json.dumps(data), encoding="utf-8")
    return comp


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_strict_fails_on_missing_translation_key(tmp_path: Path):
    comp = _make_component(
        tmp_path,
        strings={"title": "Hello", "extra": "New string"},
        translations={"de": {"title": "Hallo"}},  # missing "extra"
    )
    result = _run("--strict", str(comp))
    out = result.stdout + result.stderr
    assert result.returncode == 1, out
    assert "untranslated" in out, out


def test_missing_key_is_only_a_warning_without_strict(tmp_path: Path):
    comp = _make_component(
        tmp_path,
        strings={"title": "Hello", "extra": "New string"},
        translations={"de": {"title": "Hallo"}},  # missing "extra"
    )
    result = _run(str(comp))
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "untranslated" in out, out


def test_strict_passes_when_fully_translated(tmp_path: Path):
    comp = _make_component(
        tmp_path,
        strings={"title": "Hello"},
        translations={"de": {"title": "Hallo"}},
    )
    result = _run("--strict", str(comp))
    out = result.stdout + result.stderr
    assert result.returncode == 0, out


def test_strict_still_fails_on_stale_key(tmp_path: Path):
    comp = _make_component(
        tmp_path,
        strings={"title": "Hello"},
        translations={"de": {"title": "Hallo", "ghost": "stale"}},  # extra stale key
    )
    result = _run("--strict", str(comp))
    out = result.stdout + result.stderr
    assert result.returncode == 1, out
    assert "stale" in out, out
