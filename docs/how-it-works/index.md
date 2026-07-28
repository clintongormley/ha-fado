# How it works

The principle in action is that fades (usually executed by automations) should
be gradual and smooth, while manual actions by the user (using the switch or the
app to turn the light on or off or to change the brightness or color), should be
immediate, otherwise the user may think that something has gone wrong.

Additionally, Fado tries to do the right thing. The API should be
straightforward and simple to use, while still allowing for maximum flexibility.

_You don't need to understand all of the details explained below to use Fado.
They are provided for interest only._

## Smooth Fading

In **Settings** > **Developer tools** > **Actions**, or when configuring an
**Action** in an automation, use the `fado.fade_lights` action to:

- select one or more **target** lights
- provide a target **brightness** (where zero means turn the light off), and/or
    a **color** or **color temperature**,
- specify a **transition** time, i.e. how long the fade should last,
- optionally specify an **easing curve** which by default tries to make the fade
    smoother during the lower brightness phase.
- optionally specify a **from** starting point in case you don't want to start
    from the current state of the light.

See [**Usage: `fado.fade_lights`**](../actions/fade-lights.md) for parameter
specifications.

### Fade resolution

Fado resolves the targets list to a list of unique light entities and dispatches
a fade action for each entity, so the fade for each light begins from the state
that that light is currently in.

It uses the transition time, [**minimum delay**](../panel.md#minimum-delay) setting, and
the distance between the beginning and end states (e.g. start- and
end-brightness, or start- and end-color) to calculate the optimal number of
steps and the size of each step that the fade should use.

If the light doesn't support the specified change (for instance changing color
temperature on a light that only supports brightness), or if the light is
already in the final state, then no fade is executed.

### Fade execution

If there is an existing fade in progress then Fado cancels it and waits for it
to be cleaned up before starting the new fade.

If the light is currently on then Fado stores the current brightness level as
the `original brightness`. This is used for
[**automatic brightness restoration**](#automatic-brightness-restoration).

If a `from` parameter is specified, then it immediately sets the light to the
specified `from` state, after which the fade loop begins.

For each step in the fade loop, Fado determines the next brightness and
color/color temp values, sets them, and records how long it took. If the elapsed
time is less than the [**minimum delay**](../panel.md#minimum-delay), then it sleeps for
the remaining time before continuing with the next step. This means that the
total transition time will be at least as long as the specified `transition`
time. (It may, however, be longer if Home Assistant or the network or the light
itself is responding slowly.)

If the light supports [**native transitions**](../panel.md#native-transitions) then a short
`transition` time is used to apply a fade step to use the light's hardware to
make the fade smoother.

Fado stores the details of each fade step that is issued because it expects to
see a matching state change event which it will recognise as its own and so
knows to ignore it.

## Automatic Brightness Restoration

When you fade a light down to off and then manually turn it back on, the light
turns on at the last brightness set by the fade loop, which might be `1%`. This
is unlikely to be what you want. Instead, the integration automatically restores
the light to its `original brightness` level before the fade started.

### Example: Automatic Brightness Restoration

1. Light is at 80% brightness.
1. This value is stored as the `original brightness`.
1. You fade it to 0% (off) over 5 seconds.
1. Later, you turn the light on manually.
1. The light turns on at the last brightness the hardware is aware of, e.g. 1%.
1. Fado automatically restores the brightness to the `original brightness` value
    of 80%.

However, brightness restoration isn't always wanted. Imagine the user turns on
the light from an off state and simultaneously changes the brightness, for
instance by holding down the dimmer switch to fade the brightness up until the
switch is released. In order to distinguish between this case and the previous
case, Fado also stores the brightness at the moment the light was turned off.

### Example: Turn on and simultaneously change brightness

1. Light is at 80% brightness.
1. You turn the light off.
1. Fado stores the brightness before turning the light off as
    `previous brightness`.
1. You turn the light on and hold the dimmer switch to change the brightness.
1. Fado compares the current brightness to the `previous brightness`.
1. If they are the same then it assumes the user has just turned the light on
    and it should restore the `original brightness`.
1. If they are different then it assumes the user has also changed the
    brightness, and it stores the new brightness as `original brightness`.

## Manual interventions

During the fade loop, if Fado sees any event that it doesn't expect, that means
there has been a manual intervention (e.g. the user uses the switch or app to
switch the light on or off, or to change the brightness or color). In this case
Fado cancels the running fade and waits for any in-flight steps to finish. These
in-flight steps might overwrite the user's intended change, so once the
in-flight events have been cleared, Fado restores the intended state.

**Example 1:**

1. Light is at 80% brightness.
1. This value is stored as the `original brightness`.
1. You fade it to 0% (off) over 5 seconds.
1. When the fade reaches 30%, you turn the light off manually with the switch.
1. The fade is cancelled but an in-flight step turns the light back on at 25%.
1. Fado waits until the 25% event has been seen and no further events are
    expected.
1. Then it restores your intended state by turning the light off.
1. The stored `original brightness` remains at 80%

**Example 2:**

1. Light is at 80% brightness.
1. This value is stored as the `original brightness`.
1. You fade it to 0% (off) over 5 seconds.
1. When the fade reaches 30%, you turn the light off manually, and then back on
    again.
1. The light turns off then comes back on at 30%.
1. The fade is cancelled but an in-flight step turns the brightness to 25%.
1. Fado waits until the 25% event has been seen and no further events are
    expected.
1. Then it ignores the previous `off` state and restores your **final** intended
    state by turning the light on at the stored `original brightness` of 80%.

## Non-Dimmable Lights

Lights that do not support brightness will turn off when brightness is set to 0,
or turn on when brightness is greater than 0.

## Hybrid color/color temperature fading

Colors and color temperatures overlap, but are not the same thing. Color
temperatures consist of limited shades of white light, while colors can cover
any color in the rainbow (but typically don't display white light accurately).

Fading from one color to another is straightforward, as is fading from one color
temperature to another. Fado supports hybrid fading as well, for instance fading
from a color to a color temperature or from a color temperature to a color. It
does this by dividing the fade into two phases, where the color phase takes 70%
of the transition time, and the color temperature phase takes 30% of the
transition time.

### Fading from color to color temperature

- the color phase fades from the starting color to the closest color in the
    supported color temperature range
- the color temperature phase switches from color to color temperature at the
    crossover point and continues the fade to the target color temperature

### Fading from color temperature to color

- the color temperature phase fades from the starting color temperature to the
    last supported color temperature closest to the target color
- the color phase switches from color temperature to color at the crossover
    point and continues the fade to the target color

### Fading to color temperature where unsupported

If the user specifies a color temperature but the light only supports RGB
colors, then a best effort is made to use hue-saturation to approximate the
specified color temperature.
