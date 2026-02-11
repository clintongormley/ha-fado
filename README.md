# Fado Custom Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/clintongormley/ha-fado)](https://github.com/clintongormley/ha-fado/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration that provides smooth light
fading for brightness, colors, and color temperatures, with
automatic brightness restoration, autoconfiguration via the UI,
and support for native transitions.

## Table of Contents

- [Compatibility](#compatibility)
- [Features](#features)
- [Installation](#installation)
- [How it works](#how-it-works)
  - [Smooth Fading](#smooth-fading)
  - [Automatic Brightness Restoration](#automatic-brightness-restoration)
  - [Manual interventions](#manual-interventions)
  - [Non-Dimmable Lights](#non-dimmable-lights)
  - [Hybrid color/color temperature fading](#hybrid-colorcolor-temperature-fading)
- [State Transitions](#state-transitions)
- [Usage: `fado.fade_lights`](#usage-fadofade_lights)
- [Usage: `fado.exclude_lights` / `fado.include_lights`](#usage-fadoexclude_lights--fadoinclude_lights)
- [Autoconfiguration Panel](#autoconfiguration-panel)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Compatibility

- **Home Assistant:** 2024.1.0 or newer
- **Python:** 3.13 or newer

## Features

- Fade lights smoothly to any brightness level (0-100%) over a
  specified transition period, with easing
- Fade colors smoothly using HS, RGB, RGBW, RGBWW, XY, or color
  temperature (Kelvin)
- Hybrid transitions between color modes (e.g., color temperature
  to saturated color)
- Target lights by entity, device, area, floor, or label, or
  light groups
- Optionally specify starting values with the `from:` parameter
  for precise control
- Mostly drop-in replacement for the `light.turn_on` action
- Capability-aware: skips lights that don't support requested
  color modes
- Uses native transitions (where available) to smooth out each
  step for flicker-free fading
- Cancels fade when lights are manually adjusted
- Setting brightness to 1% automatically sets the minimum real
  brightness supported by the light
- Autoconfiguration UI to determine optimal configuration for
  individual lights
- Exclude/include lights from fades and brightness restoration
  via actions or the configuration panel
- Automatic restoration of original (pre-fade) brightness when
  turning light on

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the 3 dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/clintongormley/ha-fado` as an
   integration
5. Click "Explore & Download Repositories"
6. Search for "Fado"
7. Click "Download"
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/fado` folder to your Home
   Assistant installation:

   ```bash
   <config_directory>/custom_components/fado/
   ```

2. Restart Home Assistant

### Adding the integration

After installation and restart, add the integration via the
Home Assistant UI:

1. Go to **Settings** → **Devices & services**
2. Click **+ Add Integration**
3. Search for "Fado"
4. Click to add it

Once configured, the Fado actions will be available in
**Settings** > **Developer Tools** → **Actions**.

Before anything, you should open the
[**Autoconfiguration Panel**](#autoconfiguration-panel) in the
Home Assistant sidebar and autoconfigure your lights.

## How it works

The principle in action is that fades (usually executed by
automations) should be gradual and smooth, while manual actions
by the user (using the switch or the app to turn the light on or
off or to change the brightness or color), should be immediate,
otherwise the user may think that something has gone wrong.

Additionally, Fado tries to do the right thing. The API should
be straightforward and simple to use, while still allowing for
maximum flexibility.

*You don't need to understand all of the details explained below
to use Fado. They are provided for interest only.*

### Smooth Fading

In **Settings** > **Developer tools** > **Actions**, or when
configuring an **Action** in an automation, use the
`fado.fade_lights` action to:

- select one or more **target** lights
- provide a target **brightness** (where zero means turn the
  light off), and/or a **color** or **color temperature**,
- specify a **transition** time, i.e. how long the fade should
  last,
- optionally specify an **easing curve** which by default tries
  to make the fade smoother during the lower brightness phase.
- optionally specify a **from** starting point in case you don't
  want to start from the current state of the light.

See [**Usage: `fado.fade_lights`**](#usage-fadofade_lights) for
parameter specifications.

#### Fade resolution

Fado resolves the targets list to a list of unique light
entities and dispatches a fade action for each entity, so the
fade for each light begins from the state that that light is
currently in.

It uses the transition time,
[**minimum delay**](#minimum-delay) setting, and the distance
between the beginning and end states (e.g. start- and
end-brightness, or start- and end-color) to calculate the
optimal number of steps and the size of each step that the fade
should use.

If the light doesn't support the specified change (for instance
changing color temperature on a light that only supports
brightness), or if the light is already in the final state, then
no fade is executed.

#### Fade execution

If there is an existing fade in progress then Fado cancels it
and waits for it to be cleaned up before starting the new fade.

If the light is currently on then Fado stores the current
brightness level as the `original brightness`. This is used for
[**automatic brightness restoration**](#automatic-brightness-restoration).

If a `from` parameter is specified, then it immediately sets the
light to the specified `from` state, after which the fade loop
begins.

For each step in the fade loop, Fado determines the next
brightness and color/color temp values, sets them, and records
how long it took. If the elapsed time is less than the
[**minimum delay**](#minimum-delay), then it sleeps for the
remaining time before continuing with the next step. This means
that the total transition time will be at least as long as the
specified `transition` time. (It may, however, be longer if Home
Assistant or the network or the light itself is responding
slowly.)

If the light supports
[**native transitions**](#native-transitions) then a short
`transition` time is used to apply a fade step to use the
light's hardware to make the fade smoother.

Fado stores the details of each fade step that is issued because
it expects to see a matching state change event which it will
recognise as its own and so knows to ignore it.

### Automatic Brightness Restoration

When you fade a light down to off and then manually turn it back
on, the light turns on at the last brightness set by the fade
loop, which might be `1%`. This is unlikely to be what you want.
Instead, the integration automatically restores the light to its
`original brightness` level before the fade started.

#### Example: Automatic Brightness Restoration

1. Light is at 80% brightness.
2. This value is stored as the `original brightness`.
3. You fade it to 0% (off) over 5 seconds.
4. Later, you turn the light on manually.
5. The light turns on at the last brightness the hardware is
   aware of, e.g. 1%.
6. Fado automatically restores the brightness to the
   `original brightness` value of 80%.

However, brightness restoration isn't always wanted. Imagine the
user turns on the light from an off state and simultaneously
changes the brightness, for instance by holding down the dimmer
switch to fade the brightness up until the switch is released.
In order to distinguish between this case and the previous case,
Fado also stores the brightness at the moment the light was
turned off.

#### Example: Turn on and simultaneously change brightness

1. Light is at 80% brightness.
2. You turn the light off.
3. Fado stores the brightness before turning the light off as
   `previous brightness`.
4. You turn the light on and hold the dimmer switch to change
   the brightness.
5. Fado compares the current brightness to the
   `previous brightness`.
6. If they are the same then it assumes the user has just turned
   the light on and it should restore the `original brightness`.
7. If they are different then it assumes the user has also
   changed the brightness, and it stores the new brightness as
   `original brightness`.

### Manual interventions

During the fade loop, if Fado sees any event that it doesn't
expect, that means there has been a manual intervention (e.g.
the user uses the switch or app to switch the light on or off,
or to change the brightness or color). In this case Fado cancels
the running fade and waits for any in-flight steps to finish.
These in-flight steps might overwrite the user's intended
change, so once the in-flight events have been cleared, Fado
restores the intended state.

**Example 1:**

1. Light is at 80% brightness.
2. This value is stored as the `original brightness`.
3. You fade it to 0% (off) over 5 seconds.
4. When the fade reaches 30%, you turn the light off manually
   with the switch.
5. The fade is cancelled but an in-flight step turns the light
   back on at 25%.
6. Fado waits until the 25% event has been seen and no further
   events are expected.
7. Then it restores your intended state by turning the light
   off.
8. The stored `original brightness` remains at 80%

**Example 2:**

1. Light is at 80% brightness.
2. This value is stored as the `original brightness`.
3. You fade it to 0% (off) over 5 seconds.
4. When the fade reaches 30%, you turn the light off manually,
   and then back on again.
5. The light turns off then comes back on at 30%.
6. The fade is cancelled but an in-flight step turns the
   brightness to 25%.
7. Fado waits until the 25% event has been seen and no further
   events are expected.
8. Then it ignores the previous `off` state and restores your
   **final** intended state by turning the light on at the
   stored `original brightness` of 80%.

### Non-Dimmable Lights

Lights that do not support brightness will turn off when
brightness is set to 0, or turn on when brightness is greater
than 0.

### Hybrid color/color temperature fading

Colors and color temperatures overlap, but are not the same
thing. Color temperatures consist of limited shades of white
light, while colors can cover any color in the rainbow (but
typically don't display white light accurately).

Fading from one color to another is straightforward, as is
fading from one color temperature to another. Fado supports
hybrid fading as well, for instance fading from a color to a
color temperature or from a color temperature to a color. It
does this by dividing the fade into two phases, where the color
phase takes 70% of the transition time, and the color
temperature phase takes 30% of the transition time.

#### Fading from color to color temperature

- the color phase fades from the starting color to the closest
  color in the supported color temperature range
- the color temperature phase switches from color to color
  temperature at the crossover point and continues the fade to
  the target color temperature

#### Fading from color temperature to color

- the color temperature phase fades from the starting color
  temperature to the last supported color temperature closest to
  the target color
- the color phase switches from color temperature to color at
  the crossover point and continues the fade to the target color

#### Fading to color temperature where unsupported

If the user specifies a color temperature but the light only
supports RGB colors, then a best effort is made to use
hue-saturation to approximate the specified color temperature.

## State Transitions

### Fade state transitions

This table details how the fade is executed depending on the
initial state of the light and the target state. If the
[**`from`**](#starting-values-optional-from-block) parameter is
used, the specified values are used as the initial state.

| Initial State | Target | Action |
| --- | --- | --- |
| `state:on`, `brightness:10` | `brightness:50` | Brightness fades from 10 to 50 |
| `state:off` | `brightness:50` | Brightness fades from 0 to 50 |
| `state:on`, `hs:[10,10]` | `hs:[50,50]` | Color fades `hs:[10,10]` to `hs:[50,50]` (similar for RGB, RGBW, etc.) |
| `state:off` | `hs:[50,50]` | Color fades `hs:[0,0]` to `hs:[50,50]` (similar for RGB, RGBW, etc.) |
| `state:on`, `color_temp:2500` | `color_temp:4000` | Color temperature fades from 2500 to 4000 |
| `state:off` | `color_temp:4000` | Fades from min- or max-color temp (whichever is closest) to 4000 |
| `state:on`, `color_temp:4000` | `hs:[0,100]` | Hybrid fade from `color_temp:4000` to `hs:[0,100]` |
| `state:on`, `hs:[0,100]` | `color_temp:4000` | Hybrid fade from `hs:[0,100]` to `color_temp:4000` |



### Manual change state transitions

This table details the changes applied when Fado detects a
manual event (i.e. an event from the switch or the app):

Fado uses the `previous brightness` to distinguish between
turning a light on, and turning a light on while simultaneously
changing the brightness level:

| Old State | New State | Description |
| --- | --- | --- |
| `state:on`, `brightness: 10` | `state:off`, `brightness: None` | Light turned off. Fado stores old brightness as `previous brightness`. |
| `state:on`, `brightness: 10` | `state:on`, `brightness: 20` | Brightness changed while on. Fado stores new level as `original brightness`. |
| `state:off`, `brightness:None`, `previous brightness: 10` | `state:on`, `brightness:10` | Brightness matches `previous brightness`, so Fado restores `original brightness`. |
| `state:off`, `brightness:None` | `state:on`, `brightness:10`, `previous brightness: 20` | Brightness differs from `previous brightness`, so Fado stores it as new `original brightness`. |

## Usage: `fado.fade_lights`

Fades one or more lights to a target brightness and/or color
over a transition period.

### Parameters

#### **`target`** (required):

Specify which lights to fade using any combination of:

- **`entity_id`**: One or more light entities
  (e.g., `light.bedroom`)
- **`device_id`**: One or more device IDs
- **`area_id`**: One or more area IDs (e.g., `living_room`)
- **`floor_id`**: One or more floor IDs
- **`label_id`**: One or more label IDs

  Light groups are automatically expanded to their individual
  lights. Duplicate entities are automatically deduplicated.

#### **Transition** (optional, default: `3`):

How long the fade should take in seconds (supports decimals,
e.g., `0.5` for 500ms)

#### **Brightness parameters** (optional):

Either **`brightness_pct`** (0-100) or **`brightness`** (0-255).
A value of zero means `off`

#### **Color or color temperature parameters** (optional):

Only one target color or color temperature parameter allowed.

Either:

- **`color_temp_kelvin`**: Target color temperature in Kelvin
  (1000-40000)

or one of:

- **`hs_color`**: Target color as `[hue, saturation]` where hue
  is 0-360 and saturation is 0-100
- **`rgb_color`**: Target color as `[red, green, blue]`
  (0-255 each)
- **`rgbw_color`**: Target color as
  `[red, green, blue, white]` (0-255 each)
- **`rgbww_color`**: Target color as
  `[red, green, blue, cold_white, warm_white]` (0-255 each)
- **`xy_color`**: Target color as `[x, y]` (0-1 each)

The color parameters are converted to hue-saturation which are
used internally, while the `color_temp_kelvin` parameter is
converted to `color_temp_mireds` internally.

#### **Starting values** (optional `from:` block):

You can specify starting values to override the current light
state:

- **`from.brightness_pct`**: Starting brightness percentage
- **`from.color_temp_kelvin`**: Starting color temperature
- **`from.hs_color`**, **`from.rgb_color`**, etc.: Starting
  color (same formats as target colors)

#### **Easing curves** (optional, default `Auto`):

Changing the brightness from 100 to 101 is a 1% change, but
changing from 1 to 2 is a 100% change. This means that
brightness changes are more jarring the lower the brightness
level. Fado tries to make fading smoother by supporting easing
curves:

- **`auto`** (default): Uses `ease_in_quad` when start
  brightness is less than end brightness, and `ease_out_quad`
  when end brightness is less than start brightness
- **`linear`**: Fades in a straight line
- **`ease_in_quad`**: Starts slow
- **`ease_in_cubic`**: Starts slower
- **`ease_out_quad`**: Ends slow
- **`ease_out_cubic`**: Ends slower
- **`ease_in_out_sine`**: Smooth S curve


### Examples:

#### **Basic fade:**

```yaml
action: fado.fade_lights
target:
  entity_id: light.bedroom
data:
  brightness_pct: 50
  transition: 5
```

#### **Fade multiple lights using different targets:**

```yaml
action: fado.fade_lights
target:
  entity_id:
    - light.bedroom_wall
    - light.living_room_ceiling
    - light.outside_lights # light group
  area_id:
    - kitchen
  floor_id:
    - upstairs

data:
  brightness_pct: 80
  transition: 10
```

#### **Fade color temperature (warm to cool white) with specified starting point:**

```yaml
action: fado.fade_lights
target:
  entity_id: light.bedroom
data:
  color_temp_kelvin: 6500
  transition: 30
  from:
    color_temp_kelvin: 2700
```

#### **Fade to a specific color:**

```yaml
action: fado.fade_lights
target:
  entity_id: light.accent
data:
  hs_color: [240, 100]  # Blue
  brightness_pct: 80
  transition: 5
```

#### **Automation Example**

```yaml
automation:
  - alias: "Sunset fade"
    trigger:
      - platform: sun
        event: sunset
        offset: "-00:30:00"
    action:
      - action: fado.fade_lights
        target:
          area_id: living_room
        data:
          brightness_pct: 20
          transition: 1800 # 30 minutes
```

## Usage: `fado.exclude_lights` / `fado.include_lights`

Excludes one or more lights from Fado. Excluded lights are
ignored by fade operations and state tracking.

### Parameters

#### **`target`** (required):

Specify which lights to include or exclude using any
combination of:

- **`entity_id`**: One or more light entities
  (e.g., `light.bedroom`)
- **`device_id`**: One or more device IDs
- **`area_id`**: One or more area IDs (e.g., `living_room`)
- **`floor_id`**: One or more floor IDs
- **`label_id`**: One or more label IDs

Light groups are automatically expanded to their individual
lights. Duplicate entities are automatically deduplicated.

### Examples

#### Exclude lights

```yaml
action: fado.exclude_lights
target:
  entity_id: light.bedroom
```

#### Include lights by area

```yaml
action: fado.include_lights
target:
  area_id:
    - kitchen
    - livingroom

```

## Autoconfiguration Panel

After installation, **Fado** appears in your Home Assistant
sidebar. Click it to access the configuration panel where you
can autoconfigure each light for the smoothest fades with the
minimum of overhead.

Run **auto-configure** to automatically measure optimal step
timing, support for native transitions, and minimum real
brightness for each light

| Setting | Description | Default | Range |
| --- | --- | --- | --- |
| [**Min delay**](#minimum-delay) | Minimum delay (ms) between fade-steps without overloading slower devices | Global min delay | global - `2000` |
| [**Min brightness**](#minimum-brightness) | Minimum real brightness value that the light supports | `1` | `1` - `255` |
| [**Native transitions**](#native-transitions) | Whether to use the device's native transitions to smooth fading | `No` | `No`, `Yes`, `Disable` |
| [**Exclude**](#exclude) | Exclude this light from management by Fado | `No` | `No`, `Yes` |
| [**Log level**](#log-level) | Controls logging verbosity | `warning` | `warning`, `info`, `debug` |
| [**Global min delay**](#global-minimum-delay) | Absolute minimum delay (ms) for all lights. Per-light min delay cannot be lower | `100` | `50` - `2000` |
| [**Download diagnostics**](#download-diagnostics) | Download diagnostic data for debugging | — | — |


### Minimum delay

Autoconfiguration measures how long it takes for a light to
apply changes to brightness and to report back its new state to
Home Assistant. This minimum delay is the amount of time (in
milliseconds) that Fado will wait between each fade step.

The lower this number, the smoother the fade can be but the more
events Home Assistant needs to process. However, there is no
point in sending more frequent updates than the light can
handle. While you can configure this setting manually, it is not
recommended to set it to a lower value than that determined by
autoconfiguration.

Accepts 50ms - 2000ms and defaults to the
[global minimum delay](#global-minimum-delay). The minimum delay
for an individual light cannot be set lower than the global
minimum delay.

### Minimum brightness

Home Assistant allows setting a brightness value anywhere from 1
to 255, but internally lights often use a different scale, for
instance 1 to 100. For these lights, setting a brightness value
of 1 might result in the light being turned off instead.

Autoconfigure determines the minimum brightness value where
light is still emitted. With Fado, setting a brightness
percentage or brightness value lower than this setting will
instead apply the minimum real brightness.

### Native transitions

Some lights support native transitions, that is the light
hardware knows how to fade between two brightness levels. This
is triggered by passing a time value to the `transition`
parameter of `light.turn_on`. However, even if the light claims
to support transitions, in reality this may not be the case.
Also, the amount of time the transition takes may be very
different from the time passed to the `transition` parameter.

Autoconfiguration tests this out to determine (a) whether native
transitions are actually supported, and (b) how this affects the
minimum step delay.

By setting native transitions manually to `Disable`, Fado will
disable native transitions when autoconfiguring the minimum step
delay, and when applying fades to a light.

### Exclude

Checking the `Exclude` checkbox next to a light will prevent
Fado from fading a light and also from autorestoring the
original brightness level.

### Global minimum delay

This is the absolute minimum delay for all lights. No light may
have a custom [minimum delay](#minimum-delay) setting below this
value. It defaults to 100ms and has a minimum value of 50ms.

### Log level

See [**Troubleshooting**](#troubleshooting)

### Download diagnostics

The **Download diagnostics** link will download a JSON file
containing all of the data used by Fado for debugging purposes.
Important when submitting bug reports.


## Troubleshooting

### Enable logging via UI

Go to the
[**Autoconfiguration Panel**](#autoconfiguration-panel) by
clicking **Fado** in the Home Assistant sidebar, and adjust the
**Log level** verbosity setting:

| Level | What it shows |
| --- | --- |
| `warning` | Default. Only logs exceptions. |
| `info` | Fade start/complete, manual interventions, brightness restoration, autoconfiguration |
| `debug` | Every brightness step, expected state tracking, task cancellation internals |

For most troubleshooting, `info` level is sufficient and easier
to follow.

This log level setting is persisted across restarts.

### Known Problems

Different lights behave differently, and these differences can
create problems.

#### Rounding

The values set by Fado are not necessarily what the light
reports back. For instance, Fado sets a brightness of `50%` but
the light reports a brightness of `51%`.  Fado uses rounding to
try to match these values regardless.

#### Missing and extra events

A light may compress several actions into a single event, so
while applying a fade step the user turns the light off. This
manual intervention may be ignored by the light and so the fade
loop continues. Alternatively, maybe the light-off event is
reported and the fade step never generates an event.

When using [native transitions](#native-transitions), the light
may emit state update events which are mid-range, e.g. a fade
step is intended to move the light from brightness `50` to
brightness `65`, but the light may also report an intermediate
brightness state of `55`. Intermediate steps are recognised but
are not removed from the list of expected states as the light
should later report a final state which matches the `50->65`
change.

Fado maintains an expected-events list internally. These events
are pruned after 3 seconds so that, even if things do
occassionally go wrong, within 3 seconds the light should be
functioning normally again.


### Reporting Issues

If you encounter a bug, please
[open an issue](https://github.com/clintongormley/ha-fado/issues/new/choose)
with:

- Your Home Assistant version
- The integration version
- Debug logs showing the problem
- Diagnostic data (available from the
  [**Autoconfiguration Panel**](#autoconfiguration-panel))
- Steps to reproduce

## Development

### Running Tests

The integration includes a comprehensive test suite with 654
tests covering config flow, action handling, fade execution,
color fading, manual interruption detection, and brightness
restoration.

#### Prerequisites

Install the test dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov pytest-homeassistant-custom-component syrupy
```

> **Note:** Do not use `pip install -e .` (editable install) as
> it conflicts with
> `pytest-homeassistant-custom-component`'s custom component
> discovery mechanism.

#### Running Tests

Run all tests:

```bash
pytest tests/ -v
```

Run tests with coverage report:

```bash
pytest tests/ --cov=custom_components.fado --cov-report=term-missing -v
```

Run a specific test file:

```bash
pytest tests/test_fade_execution.py -v
```

#### Test Coverage

The test suite achieves 100% code coverage and includes tests
for:

- **Config flow** (`test_config_flow.py`): User setup, import
  flow, options validation
- **Integration setup** (`test_init.py`): Action registration,
  storage loading, unload cleanup
- **Action handling** (`test_actions.py`): Entity ID formats,
  group expansion, default parameters
- **Fade execution** (`test_fade_execution.py`): Fade up/down,
  turn off at 0%, non-dimmable lights
- **Color parameters** (`test_color_params.py`): Color
  conversions, validation, `from:` parameter
- **Capability filtering** (`test_capability_filtering.py`):
  Light capability detection, unsupported mode handling
- **Step generation** (`test_step_generation.py`): Hue
  interpolation, hybrid transitions
- **Planckian locus** (`test_planckian_locus.py`): Color
  temperature to HS conversions
- **Manual interruption** (`test_manual_interruption.py`):
  Brightness/color change detection, fade cancellation
- **Brightness restoration**
  (`test_brightness_restoration.py`): Restore on turn-on,
  storage persistence
- **Exclude/include actions** (`test_exclude_action.py`):
  Action registration, flag persistence, fade filtering, panel
  notification
- **Event waiting** (`test_event_waiting.py`):
  Condition-based event waiting, stale value pruning

### Continuous Integration

Tests run automatically on push and pull requests via GitHub
Actions. The workflow tests against Python 3.13.

## License

MIT License - feel free to modify and redistribute
