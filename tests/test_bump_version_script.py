"""Tests for bin/bump-version.sh."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "bin" / "bump-version.sh"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _make_manifest(tmp_path: Path, version: str = "1.1.1") -> Path:
    manifest = tmp_path / "custom_components" / "fado" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(f'{{\n  "domain": "fado",\n  "version": "{version}"\n}}\n')
    return manifest


def test_validate_rejects_bad_semver_and_writes_nothing(tmp_path: Path):
    manifest = _make_manifest(tmp_path)
    before = manifest.read_text()

    result = _run(tmp_path, "--validate", "not-a-version")
    assert result.returncode != 0
    assert "semver" in (result.stdout + result.stderr).lower()

    # --validate must not touch the file.
    assert manifest.read_text() == before


def test_validate_accepts_good_semver(tmp_path: Path):
    _make_manifest(tmp_path)
    result = _run(tmp_path, "--validate", "1.2.0")
    assert result.returncode == 0


def test_validate_accepts_prerelease_suffix(tmp_path: Path):
    _make_manifest(tmp_path)
    result = _run(tmp_path, "--validate", "1.2.0-rc.1")
    assert result.returncode == 0


def test_normal_bump_rewrites_manifest(tmp_path: Path):
    manifest = _make_manifest(tmp_path, "1.1.1")
    result = _run(tmp_path, "1.2.0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"version": "1.2.0"' in manifest.read_text()
    assert '"version": "1.1.1"' not in manifest.read_text()


def test_bump_rejects_bad_semver(tmp_path: Path):
    manifest = _make_manifest(tmp_path)
    before = manifest.read_text()
    result = _run(tmp_path, "not-a-version")
    assert result.returncode != 0
    assert "semver" in (result.stdout + result.stderr).lower()
    assert manifest.read_text() == before


def test_bump_fails_when_manifest_missing(tmp_path: Path):
    result = _run(tmp_path, "1.2.0")
    assert result.returncode != 0
    assert "not found" in (result.stdout + result.stderr).lower()
