# Claude Code Instructions

## Git Workflow

- **NEVER commit directly to main** - always create a feature branch first
- **Branch naming**: Use descriptive names like `fix/cancel-autoconfigure` or `ci/add-hacs-validation`. **Never** include version numbers in branch names (e.g. avoid `release/0.90.1`) — HACS scans all branches and will complain about non-compliant ones, even after deletion
- Do NOT merge PRs automatically - wait for user approval before merging
- When merging a PR (after approval), delete the feature branch

## Changelog

- Record **all user-facing changes** in `CHANGES.md` under the `## [Unreleased]` section, using the [Keep a Changelog](https://keepachangelog.com/) categories (`Added`, `Changed`, `Fixed`, `Removed`, etc.)
- Prefix any breaking change with **BREAKING** and describe the action users must take to upgrade

## Documentation

- `docs/` is the **published** mkdocs site source (<https://clintongormley.github.io/ha-fado/docs/>).
  User-facing documentation changes go there, not in `README.md` — the README is
  a stub that links to the site.
- `docs/superpowers/` is gitignored. Brainstorming specs and implementation plans
  written there are **local working files**; do not commit them.
- Build the site with `scripts/build_site.sh`; preview docs alone with `mkdocs serve`.

## Code Quality

- Before creating a PR, always run `ruff check .` and `ruff format .` to fix any linting issues
- Before creating a PR, run `npx pyright` to check for Pylance/type errors and fix any that can be fixed
- Before creating a release always update the docs and translations and tests
- The `manifest.json` keys must be sorted: `domain`, `name` first, then all remaining keys in alphabetical order

## Frontend design system

The frontend uses a `--fado-*` token layer and conventions documented in
`docs/development/design-system.md`. Follow it: use the `--fado-*` tokens (never
hardcode chrome colour/spacing), the guarded `ha-*` control helpers, and the
720px `_compact` breakpoint. Pure logic goes in `fado-logic.js` with a vitest
test (`npm test`).
