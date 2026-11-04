# Installation

Which catalog you install Fado from depends on your version of Home Assistant.
Both offer the same listing, so use whichever your version has. Installing from
a catalog is better than copying the files by hand, because the catalog tells
you when an update is available.

=== "Home Assistant 2026.11 or newer: Marketplace"

    The Marketplace is built into Home Assistant, so you don't need to install
    anything separately. The first time you open it, it shows a warning that
    you need to accept before you can install anything.

    [![Open this repository in your Home Assistant instance.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado)

    Or install by searching in the Marketplace:

    1. Go to **Settings** > **Marketplace**
    1. Search for "Fado"
    1. Click **Install**
    1. Restart Home Assistant

=== "Home Assistant 2026.10 or older: HACS"

    Fado is available in the default HACS repository.

    [![Open this repository in your Home Assistant instance.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado)

    Or install by searching in HACS:

    1. Open HACS in your Home Assistant instance
    1. Search for "Fado"
    1. Click "Download"
    1. Restart Home Assistant

=== "Manual"

    1. Copy the `custom_components/fado` folder to your Home Assistant installation:

        ```bash
        <config_directory>/custom_components/fado/
        ```

    1. Restart Home Assistant

## Adding the integration

After installation and restart, add the integration via the Home Assistant UI:

1. Go to **Settings** → **Devices & services**
1. Click **+ Add Integration**
1. Search for "Fado"
1. Click to add it

Once configured, the Fado actions will be available in **Settings** >
**Developer Tools** → **Actions**.

Before anything, you should open the
[**Autoconfiguration Panel**](panel.md) in the Home Assistant
sidebar and autoconfigure your lights.
