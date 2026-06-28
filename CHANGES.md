# Changes

All notable user-facing changes to this integration are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/). Entries marked
**BREAKING** require user action when upgrading.

## [Unreleased]

### Added

- Frontend: responsive layout — on narrow screens the lights table becomes
  collapsible per-light cards with a "needs setup" indicator and a per-area
  roll-up; touch-friendly controls.
- Frontend internationalisation: the Fado panel/card UI now loads per-language
  catalogs (`frontend/translations/<lang>.json`); English is the built-in
  fallback. Non-English UI translations are AI-generated and pending native
  review — corrections welcome.
- A dismissable banner that nudges users whose Home Assistant language Fado does
  not yet support to request a translation via a prefilled GitHub issue.

### Changed

- Frontend: configuration panel/card now use HA's themed select control and a
  `--fado-*` design-token layer for consistent theming.
- Panel/card UI strings are now localised via the new i18n layer (English output
  unchanged).

### Removed

- **BREAKING: Removed the Log level selector from the configuration panel.**
  Fado logs through Home Assistant's standard logger, so adjust its verbosity
  the usual way instead — **Enable debug logging** on the integration page, or a
  `logger:` entry in `configuration.yaml`. See the Troubleshooting section of
  the README. If you previously raised the level via the panel, that choice is
  no longer re-applied on restart; set it the standard way to make it persist.

## [2.0.0] - 2026-06-14

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

- **Unconfigured-light alerts now use Repairs instead of a persistent
  notification.** When Fado detects lights that haven't been autoconfigured, it
  raises an issue under **Settings → System → Repairs** (with a learn-more link
  to the Fado panel/dashboard) rather than showing a persistent notification.
  The issue clears automatically once every light is configured. The
  enable/disable option is unchanged in effect; its label is now "Notify about
  unconfigured lights". The repair text is fully translated across all supported
  languages.

### Fixed

- **Native-transition fades no longer mis-detect manual intervention.** When a
  fade used a light's native transition, the bulb's own state reports could lag
  or coalesce across Fado's commanded steps (e.g. reporting `76→71` then
  `71→46`, skipping the commanded `60`). Fado mistook these legitimate
  intermediate reports for manual intervention and triggered a spurious restore,
  interrupting the fade — often more than once a day. Fado now uses
  moving-anchor matching for native fades, anchoring each step's match window to
  the last reported value so lagging/coalesced reports are absorbed while
  genuine manual changes are still detected.

- **Unavailable light groups are no longer flagged as needing configuration.**
  When every member of a light group is unavailable, the group's own state
  becomes `unavailable` and Home Assistant strips its attributes — including the
  member list Fado uses to recognise it as a group, so the group looked like an
  ordinary unconfigured light. Fado now skips unavailable lights both when
  counting unconfigured lights for the Repairs issue and when listing lights in
  the configuration panel, so such a group is no longer mistaken for one. Any
  existing configuration for an unavailable light is preserved until the light
  is actually removed.
