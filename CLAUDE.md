# Claude Code Instructions

## Git Workflow

- **NEVER commit directly to main** - always create a feature branch first
- **Branch naming**: Use descriptive names like `fix/cancel-autoconfigure` or `ci/add-hacs-validation`. **Never** include version numbers in branch names (e.g. avoid `release/0.90.1`) — HACS scans all branches and will complain about non-compliant ones, even after deletion
- All changes must go through a Pull Request (PR)
- Do NOT merge PRs automatically - wait for user approval before merging
- When merging a PR (after approval), delete the feature branch

## Code Quality

- Before creating a PR, always run `ruff check .` and `ruff format .` to fix any linting issues
- Before creating a PR, run `npx pyright` to check for Pylance/type errors and fix any that can be fixed
- Before creating a release always update the docs and translations and tests
- The `manifest.json` keys must be sorted: `domain`, `name` first, then all remaining keys in alphabetical order
