# State transitions

## Fade state transitions

This table details how the fade is executed depending on the initial state of
the light and the target state. If the
[**`from`**](../actions/fade-lights.md#starting-values-optional-from-block) parameter is used, the
specified values are used as the initial state.

| Initial State                 | Target            | Action                                                                 |
| ----------------------------- | ----------------- | ---------------------------------------------------------------------- |
| `state:on`, `brightness:10`   | `brightness:50`   | Brightness fades from 10 to 50                                         |
| `state:off`                   | `brightness:50`   | Brightness fades from 0 to 50                                          |
| `state:on`, `hs:[10,10]`      | `hs:[50,50]`      | Color fades `hs:[10,10]` to `hs:[50,50]` (similar for RGB, RGBW, etc.) |
| `state:off`                   | `hs:[50,50]`      | Color fades `hs:[0,0]` to `hs:[50,50]` (similar for RGB, RGBW, etc.)   |
| `state:on`, `color_temp:2500` | `color_temp:4000` | Color temperature fades from 2500 to 4000                              |
| `state:off`                   | `color_temp:4000` | Fades from min- or max-color temp (whichever is closest) to 4000       |
| `state:on`, `color_temp:4000` | `hs:[0,100]`      | Hybrid fade from `color_temp:4000` to `hs:[0,100]`                     |
| `state:on`, `hs:[0,100]`      | `color_temp:4000` | Hybrid fade from `hs:[0,100]` to `color_temp:4000`                     |

## Manual change state transitions

This table details the changes applied when Fado detects a manual event (i.e. an
event from the switch or the app):

Fado uses the `previous brightness` to distinguish between turning a light on,
and turning a light on while simultaneously changing the brightness level:

| Old State                                                 | New State                                              | Description                                                                                    |
| --------------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| `state:on`, `brightness: 10`                              | `state:off`, `brightness: None`                        | Light turned off. Fado stores old brightness as `previous brightness`.                         |
| `state:on`, `brightness: 10`                              | `state:on`, `brightness: 20`                           | Brightness changed while on. Fado stores new level as `original brightness`.                   |
| `state:off`, `brightness:None`, `previous brightness: 10` | `state:on`, `brightness:10`                            | Brightness matches `previous brightness`, so Fado restores `original brightness`.              |
| `state:off`, `brightness:None`                            | `state:on`, `brightness:10`, `previous brightness: 20` | Brightness differs from `previous brightness`, so Fado stores it as new `original brightness`. |
