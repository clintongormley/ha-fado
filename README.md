# Fado Light Fader

[![Marketplace and HACS](https://img.shields.io/badge/Marketplace%20and%20HACS-Default-blue.svg)](https://clintongormley.github.io/ha-fado/docs/installation/)
[![GitHub Release](https://img.shields.io/github/v/release/clintongormley/ha-fado)](https://github.com/clintongormley/ha-fado/releases)
[![Active Installations](https://img.shields.io/badge/dynamic/json?label=Active%20Installations&query=%24.fado.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&color=blue&logo=home-assistant)](https://analytics.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration, available from the Home Assistant
Marketplace and from HACS, that provides smooth light fading for brightness,
colors, and color temperatures, with automatic brightness restoration,
autoconfiguration via the UI, and support for native transitions.

**▶ [Try the interactive demo](https://clintongormley.github.io/ha-fado/)** —
start a bedtime fade, interrupt it at the wall switch, and watch Fado restore
the brightness you chose.

**📖 [Read the documentation](https://clintongormley.github.io/ha-fado/docs/)** —
installation, the `fado.fade_lights` action reference, the autoconfiguration
panel, and troubleshooting.

## Install

On Home Assistant 2026.11 or newer, go to **Settings → Marketplace**, search for
**Fado Light Fader** and select **Install**. The Marketplace is built into Home
Assistant, so you don't need to install anything separately. The first time you
open it, it shows a warning that you need to accept before you can install
anything.

On Home Assistant 2026.10 or older, search for **Fado Light Fader** in HACS and
install it from there.

This button opens Fado on either version:

[![Open this repository in your Home Assistant instance.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado)

Then restart Home Assistant and add the integration from **Settings → Devices &
Services**. Full instructions:
[Installation](https://clintongormley.github.io/ha-fado/docs/installation/).

## Contributing

Tests and how to build the documentation site are covered in
[Development](https://clintongormley.github.io/ha-fado/docs/development/).

## Credits

The interactive demo was originally created by
[Florian Horner](https://github.com/florianhorner)
([source](https://github.com/florianhorner/fado-light-fader-demo), 0BSD) and is
included here with permission.

## License

Licensed under the [MIT License](LICENSE) — feel free to modify and redistribute.
