# HACS Readiness Design

Preparing the ha_fade_lights integration for distribution via HACS (Home Assistant Community Store).

## Goals

- Fix version mismatch between manifest.json and git tags
- Automate the release process via GitHub Actions
- Polish README with badges and troubleshooting info
- Add issue templates for better user feedback

## Non-goals

- Adding screenshots (deferred - owner will add later)
- CONTRIBUTING.md (premature - no contributors yet)
- Changelog file (GitHub release notes suffice)
- CI testing workflow (already works locally)

## Changes

### 1. Version Alignment

**Problem:** manifest.json says `1.0.0` but git tags are `v0.0.x`.

**Solution:** Update manifest.json version to `0.0.2` to match current tag.

**Versioning scheme going forward:**
- `0.0.x` - Patch releases (bug fixes)
- `0.1.0`, `0.2.0` - Minor releases (new features)
- `1.0.0` - When considered stable for general use

**File:** `custom_components/fade_lights/manifest.json`

### 2. Automated Release Workflow

**Trigger:** Push tag matching `v*.*.*`

**Steps:**
1. Extract version from tag (strip `v` prefix)
2. Read version from manifest.json
3. Fail if versions don't match
4. Create GitHub Release with auto-generated notes

**Release process becomes:**
```bash
# 1. Update manifest.json version
# 2. Commit: "Bump version to X.Y.Z"
# 3. Tag and push:
git tag vX.Y.Z
git push origin vX.Y.Z
# 4. GitHub Action creates release automatically
```

**File:** `.github/workflows/release.yml`

### 3. README Polish

**Additions:**
- Badges: HACS, GitHub Release, License
- Troubleshooting section with debug logging instructions
- Update test count (51 -> 70)
- Compatibility section noting HA version requirements

**File:** `README.md`

### 4. Issue Templates

YAML-based templates for structured form fields.

**Bug Report template:**
- HA version, integration version
- Steps to reproduce
- Expected vs actual behavior
- Debug logs with instructions
- Light entity details

**Feature Request template:**
- Use case description
- Proposed solution
- Alternatives considered

**Config file:**
- Blank issue escape hatch
- Links to docs for questions

**Files:**
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`

## File Summary

| File | Action |
|------|--------|
| `custom_components/fade_lights/manifest.json` | Modify - version to 0.0.2 |
| `.github/workflows/release.yml` | Create |
| `README.md` | Modify |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Create |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Create |
| `.github/ISSUE_TEMPLATE/config.yml` | Create |

## Future Considerations

- Add screenshots/GIF demo when available
- CONTRIBUTING.md when contributors appear
- Conventional commits + automated changelog if release frequency increases
