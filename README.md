# Fado Light Fader

[![HACS Default](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/clintongormley/ha-fado)](https://github.com/clintongormley/ha-fado/releases)
[![Active Installations](https://img.shields.io/badge/dynamic/json?label=Active%20Installations&query=%24.fado.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&color=blue&logo=home-assistant)](https://analytics.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration, available in the HACS default store, that
provides smooth light fading for brightness, colors, and color temperatures,
with automatic brightness restoration, autoconfiguration via the UI, and
support for native transitions.

**▶ [Try the interactive demo](https://clintongormley.github.io/ha-fado/)** —
start a bedtime fade, interrupt it at the wall switch, and watch Fado restore
the brightness you chose.

**📖 [Read the documentation](https://clintongormley.github.io/ha-fado/docs/)** —
installation, the `fado.fade_lights` action reference, the autoconfiguration
panel, and troubleshooting.

## Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado)

Or, in HACS, search for **Fado Light Fader**, install it, restart Home
Assistant, then add the integration from **Settings → Devices & Services**.
Full instructions: [Installation](https://clintongormley.github.io/ha-fado/docs/installation/).

## Contributing

Tests, the design system, and how to build the documentation site are covered in
[Development](https://clintongormley.github.io/ha-fado/docs/development/).

## Credits

The interactive demo was originally created by
[Florian Horner](https://github.com/florianhorner)
([source](https://github.com/florianhorner/fado-light-fader-demo), 0BSD) and is
included here with permission.

## License

Licensed under the [MIT License](LICENSE) — feel free to modify and redistribute.
