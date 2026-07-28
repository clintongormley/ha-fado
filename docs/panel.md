# Autoconfiguration panel

After installation, **Fado** appears in your Home Assistant sidebar. Click it to
access the configuration panel where you can autoconfigure each light for the
smoothest fades with the minimum of overhead.

Run **auto-configure** to automatically measure optimal step timing, support for
native transitions, and minimum real brightness for each light

## Settings

| Setting                                           | Description                                                                     | Default          | Range                  |
| ------------------------------------------------- | ------------------------------------------------------------------------------- | ---------------- | ---------------------- |
| [**Min delay**](#minimum-delay)                   | Minimum delay (ms) between fade-steps without overloading slower devices        | Global min delay | global - `2000`        |
| [**Min brightness**](#minimum-brightness)         | Minimum real brightness value that the light supports                           | `1`              | `1` - `255`            |
| [**Native transitions**](#native-transitions)     | Whether to use the device's native transitions to smooth fading                 | `No`             | `No`, `Yes`, `Disable` |
| [**Exclude**](#exclude)                           | Exclude this light from management by Fado                                      | `No`             | `No`, `Yes`            |
| [**Global min delay**](#global-minimum-delay)     | Absolute minimum delay (ms) for all lights. Per-light min delay cannot be lower | `100`            | `50` - `2000`          |
| [**Download diagnostics**](#download-diagnostics) | Download diagnostic data for debugging                                          | —                | —                      |

### Minimum delay

Autoconfiguration measures how long it takes for a light to apply changes to
brightness and to report back its new state to Home Assistant. This minimum
delay is the amount of time (in milliseconds) that Fado will wait between each
fade step.

The lower this number, the smoother the fade can be but the more events Home
Assistant needs to process. However, there is no point in sending more frequent
updates than the light can handle. While you can configure this setting
manually, it is not recommended to set it to a lower value than that determined
by autoconfiguration.

Accepts 50ms - 2000ms and defaults to the
[global minimum delay](#global-minimum-delay). The minimum delay for an
individual light cannot be set lower than the global minimum delay.

### Minimum brightness

Home Assistant allows setting a brightness value anywhere from 1 to 255, but
internally lights often use a different scale, for instance 1 to 100. For these
lights, setting a brightness value of 1 might result in the light being turned
off instead.

Autoconfigure determines the minimum brightness value where light is still
emitted. With Fado, setting a brightness percentage or brightness value lower
than this setting will instead apply the minimum real brightness.

### Native transitions

Some lights support native transitions, that is the light hardware knows how to
fade between two brightness levels. This is triggered by passing a time value to
the `transition` parameter of `light.turn_on`. However, even if the light claims
to support transitions, in reality this may not be the case. Also, the amount of
time the transition takes may be very different from the time passed to the
`transition` parameter.

Autoconfiguration tests this out to determine (a) whether native transitions are
actually supported, and (b) how this affects the minimum step delay.

By setting native transitions manually to `Disable`, Fado will disable native
transitions when autoconfiguring the minimum step delay, and when applying fades
to a light.

### Exclude

Checking the `Exclude` checkbox next to a light will prevent Fado from fading a
light and also from autorestoring the original brightness level.

### Global minimum delay

This is the absolute minimum delay for all lights. No light may have a custom
[minimum delay](#minimum-delay) setting below this value. It defaults to 100ms
and has a minimum value of 50ms.

### Download diagnostics

The **Download diagnostics** link will download a JSON file containing all of
the data used by Fado for debugging purposes. Important when submitting bug
reports.

## Disabling the sidebar panel

By default, Fado adds a **Fado Light Fader** entry to the Home Assistant
sidebar, visible to all users. If you prefer to control who can access the Fado
UI, you can disable the sidebar panel and use a
[custom dashboard](#custom-autoconfiguration-dashboard) instead.

To disable the sidebar panel:

1. Go to **Settings → Devices & Services → Fado → Configure**
1. Uncheck **Show sidebar panel**
1. Click **Submit**

The sidebar entry will be removed immediately. The Fado card and dashboard
strategy remain available for use in any Lovelace dashboard.

## Custom autoconfiguration dashboard

Fado provides a custom Lovelace card (`custom:fado-card`) and a dashboard
strategy (`custom:fado`) that give you the same autoconfiguration UI as the
sidebar panel, but with full control over dashboard visibility and placement.

### Adding the Fado card to an existing dashboard

You can add the Fado card to any Lovelace dashboard:

1. Edit your dashboard and click **Add Card**
1. Select the **By card** tab, then search for **Fado Light Fader** (in Home
    Assistant 2026.6+ the card picker opens on the **By entity** tab; the Fado
    card configures the whole integration rather than a single entity, so it
    only appears under **By card**)
1. Add the card

Or add it manually in YAML mode:

```yaml
type: custom:fado-card
```

For best results, use the card in a **Panel** view (single card filling the full
page).

### Creating a dedicated Fado dashboard

To create a standalone Fado dashboard using the built-in strategy:

1. Go to **Settings → Dashboards → Add Dashboard**
1. Set the URL to something like `lovelace-fado`
1. Configure visibility (e.g. admin only, or specific users)
1. Open the dashboard and switch to raw configuration editor (**Edit Dashboard →
    Raw configuration editor**)
1. Replace the contents with:

```yaml
strategy:
  type: custom:fado
```

This creates a full-page dashboard with the Fado card. You can then control
which users see it via the dashboard visibility settings.

## Repairs

When Fado detects lights that haven't been autoconfigured yet, it raises an
issue under **Settings → System → Repairs** to prompt you to configure them. The
issue clears automatically once every light is configured.

You can control this behaviour in **Settings → Devices & Services → Fado →
Configure**:

- **Notify about unconfigured lights** — Uncheck to stop raising the repair
    entirely.
- **Dashboard URL** — When the sidebar panel is disabled, the repair's
    learn-more link points to this URL (e.g. `/lovelace-fado/0`). Leave blank to
    omit the link.
