# Changes

All notable user-facing changes to this integration are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/). Entries marked
**BREAKING** require user action when upgrading.

## [Unreleased]

### Added

- **`fado.fade_lights` now accepts an `only_if` filter** to restrict a fade to
  lights that are currently in a given power state. Set `only_if: on` to fade
  only lights that are already on, or `only_if: off` to fade only lights that
  are off; leave it unset (the default) to fade every targeted light, exactly as
  before. Available under the action's advanced options in the UI.

### Changed

- **BREAKING: Configuring Fado is now admin-only.** Every `fado/*` WebSocket
  command (`get_lights`, `save_light_config`, `autoconfigure`,
  `test_native_transitions`, `get_settings`, `save_settings`) previously
  accepted any logged-in user; they now require an administrator account. As a
  result:
  - The sidebar panel is no longer shown to non-admin users.
  - The Fado Lovelace card and dashboard strategy (which share the same
    configuration UI) now display an "administrator access is required" notice
    for non-admin users instead of the configuration table.
  - The `fado.exclude_lights` and `fado.include_lights` services change
    per-light configuration, so they are now admin-only as well. Automations
    and scripts (which run without a user context) are unaffected; only direct
    calls by a non-admin user are rejected. The `fado.fade_lights` service is a
    runtime operation and remains available to everyone.

  **Action required:** grant admin rights to any user who needs to manage Fado
  settings.
