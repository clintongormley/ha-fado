# Installation

=== "HACS (recommended)"

    Fado is available in the default HACS repository.

    [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&owner=clintongormley&repository=ha-fado)

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
**Autoconfiguration Panel** in the Home Assistant
sidebar and autoconfigure your lights.
