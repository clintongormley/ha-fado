"""Tests for bin/release.sh."""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "bin" / "release.sh"


def _clean_env(extra: dict | None = None) -> dict:
    """Return os.environ with all GIT_* vars stripped, plus any extras.

    Without this, subprocess git calls in tests inherit GIT_DIR / GIT_WORK_TREE /
    GIT_INDEX_FILE from a parent context (e.g. a pre-push hook) and operate on
    the wrong repo.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if extra:
        env.update(extra)
    return env


def _git(*args: str, cwd: Path, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run a git command with GIT_* env scrubbed."""
    return subprocess.run(["git", *args], cwd=cwd, check=check, env=_clean_env(), **kwargs)


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=_clean_env(),
    )


def test_rejects_invalid_semver(tmp_path: Path):
    result = _run(tmp_path, "not-a-version")
    assert result.returncode != 0
    assert "semver" in (result.stdout + result.stderr).lower()


def test_accepts_alpha_suffix(tmp_path: Path):
    """Pre-flight should accept alpha pre-release suffix at the semver check.
    Other pre-flights (clean tree, on main, etc.) will still fail in tmp_path,
    so we only check that the error is NOT a semver error."""
    result = _run(tmp_path, "1.2.0-alpha.1")
    combined = (result.stdout + result.stderr).lower()
    assert "semver" not in combined


def test_accepts_beta_suffix(tmp_path: Path):
    result = _run(tmp_path, "1.2.0-beta.2")
    combined = (result.stdout + result.stderr).lower()
    assert "semver" not in combined


def test_accepts_rc_suffix(tmp_path: Path):
    result = _run(tmp_path, "1.2.0-rc.1")
    combined = (result.stdout + result.stderr).lower()
    assert "semver" not in combined


def _init_repo(tmp_path: Path, *, branch: str = "main", dirty: bool = False) -> Path:
    """Create a tiny git repo with the manifest version file on the named branch."""
    _git("init", "-q", "-b", branch, cwd=tmp_path)
    _git("config", "user.email", "t@test", cwd=tmp_path)
    _git("config", "user.name", "t", cwd=tmp_path)

    (tmp_path / "custom_components" / "fado").mkdir(parents=True)
    (tmp_path / "custom_components" / "fado" / "manifest.json").write_text(
        '{\n  "domain": "fado",\n  "version": "1.1.1"\n}\n'
    )
    # bin/bump-version.sh and bin/release.sh must be present in the test repo so
    # release.sh can call its sibling bump script via $(dirname "$0").
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "release.sh").write_text(SCRIPT.read_text())
    (tmp_path / "bin" / "release.sh").chmod(0o755)
    bump = REPO_ROOT / "bin" / "bump-version.sh"
    (tmp_path / "bin" / "bump-version.sh").write_text(bump.read_text())
    (tmp_path / "bin" / "bump-version.sh").chmod(0o755)

    _git("add", ".", cwd=tmp_path)
    _git("commit", "-qm", "init", cwd=tmp_path)
    _git("tag", "v1.1.1", cwd=tmp_path)

    if dirty:
        (tmp_path / "dirt").write_text("x")

    return tmp_path


def test_rejects_non_main_branch(tmp_path: Path):
    _init_repo(tmp_path, branch="feature")
    result = _run(tmp_path, "1.2.0")
    assert result.returncode != 0
    assert "main" in (result.stdout + result.stderr).lower()


def test_rejects_dirty_tree(tmp_path: Path):
    _init_repo(tmp_path, dirty=True)
    result = _run(tmp_path, "1.2.0")
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "clean" in combined or "dirty" in combined or "uncommitted" in combined


def test_rejects_existing_tag(tmp_path: Path):
    _init_repo(tmp_path)
    result = _run(tmp_path, "1.1.1")  # tag v1.1.1 already exists
    assert result.returncode != 0
    assert "tag" in (result.stdout + result.stderr).lower()


def test_rejects_main_behind_origin(tmp_path: Path):
    """If local main has fewer commits than origin/main, fail."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)

    local = tmp_path / "local"
    local.mkdir()
    _init_repo(local)
    _git("remote", "add", "origin", str(origin), cwd=local)
    _git("push", "-q", "origin", "main", "--tags", cwd=local)

    other = tmp_path / "other"
    _git("clone", "-q", str(origin), str(other), cwd=tmp_path)
    _git("config", "user.email", "t@test", cwd=other)
    _git("config", "user.name", "t", cwd=other)
    (other / "new.txt").write_text("x")
    _git("add", ".", cwd=other)
    _git("commit", "-qm", "new", cwd=other)
    _git("push", "-q", "origin", "main", cwd=other)

    result = _run(local, "1.2.0")
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "up to date" in combined or "behind" in combined


def test_integration_no_push_bumps_manifest_on_chore_release_branch(tmp_path: Path):
    _init_repo(tmp_path)
    result = _run(tmp_path, "1.2.0", "--no-push")
    assert result.returncode == 0, result.stdout + result.stderr

    # Version-less chore/release branch exists (HACS rejects version numbers in
    # branch names, so the release branch is deliberately version-less).
    branches = _git(
        "branch", "--list", "chore/release", cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "chore/release" in branches

    _git("checkout", "-q", "chore/release", cwd=tmp_path)

    manifest = (tmp_path / "custom_components" / "fado" / "manifest.json").read_text()
    assert '"version": "1.2.0"' in manifest

    # The release branch carries a clear chore: release marker commit.
    last_msg = _git(
        "log", "-1", "--format=%s", cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert "release v1.2.0" in last_msg, f"unexpected last commit message: {last_msg!r}"


def test_succeeds_when_version_already_at_target(tmp_path: Path):
    """When the manifest is already bumped on main (e.g. in an earlier feature
    commit), the release script must still succeed: create a chore: release
    marker commit (possibly empty) so the tag points at a clear release commit."""
    _init_repo(tmp_path)  # version at 1.1.1, tag v1.1.1

    (tmp_path / "custom_components" / "fado" / "manifest.json").write_text(
        '{\n  "domain": "fado",\n  "version": "1.2.0"\n}\n'
    )
    _git("add", ".", cwd=tmp_path)
    _git("commit", "-qm", "feat: pre-bumped version", cwd=tmp_path)

    result = _run(tmp_path, "1.2.0", "--no-push")
    assert result.returncode == 0, result.stdout + result.stderr

    _git("checkout", "-q", "chore/release", cwd=tmp_path)
    last_msg = _git(
        "log", "-1", "--format=%s", cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert "release v1.2.0" in last_msg, f"unexpected last commit message: {last_msg!r}"

    manifest = (tmp_path / "custom_components" / "fado" / "manifest.json").read_text()
    assert '"version": "1.2.0"' in manifest


def test_pushes_and_opens_pr(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    # Shim gh and git push into a fake bin dir that records calls. Keep fake_bin
    # outside the git repo so it doesn't dirty the working tree.
    fake_bin = tmp_path / "fake_bin"
    fake_bin.mkdir()
    log = tmp_path / "calls.log"

    (fake_bin / "gh").write_text(
        f'#!/usr/bin/env bash\necho "gh $*" >> "{log}"\necho https://github.com/fake/repo/pull/1\n'
    )
    (fake_bin / "gh").chmod(0o755)

    real_git = subprocess.check_output(["which", "git"], text=True).strip()
    (fake_bin / "git").write_text(
        f'#!/usr/bin/env bash\nif [ "$1" = "push" ]; then echo "git $*" >> "{log}"; exit 0; fi\n'
        f'exec {real_git} "$@"\n'
    )
    (fake_bin / "git").chmod(0o755)

    env = _clean_env({"PATH": f"{fake_bin}:{os.environ['PATH']}"})
    result = subprocess.run(
        ["bash", str(SCRIPT), "1.2.0"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    call_log = log.read_text()
    assert "git push" in call_log
    assert "gh pr create" in call_log
    assert "chore/release" in call_log


def test_does_not_leak_to_parent_git_dir_via_env(tmp_path: Path, monkeypatch):
    """If GIT_DIR is set in the env (e.g. by a hook or wrapper), tests must not
    accidentally write to that repo."""
    parent = tmp_path / "parent_repo"
    parent.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(parent)], check=True)
    parent_git = parent / ".git"
    config_before = (parent_git / "config").read_text()

    monkeypatch.setenv("GIT_DIR", str(parent_git))

    fixture = tmp_path / "fixture"
    fixture.mkdir()
    _init_repo(fixture)

    config_after = (parent_git / "config").read_text()
    assert config_before == config_after, (
        f"_init_repo leaked into GIT_DIR config:\n--- before ---\n{config_before}\n"
        f"--- after ---\n{config_after}"
    )
