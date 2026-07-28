# `fado.fade_lights`

Fades one or more lights to a target brightness and/or color over a transition
period.

## Parameters

### **`target`** (required):

Specify which lights to fade using any combination of:

- **`entity_id`**: One or more light entities (e.g., `light.bedroom`)

- **`device_id`**: One or more device IDs

- **`area_id`**: One or more area IDs (e.g., `living_room`)

- **`floor_id`**: One or more floor IDs

- **`label_id`**: One or more label IDs

Light groups are automatically expanded to their individual lights. Duplicate
entities are automatically deduplicated.

### **Transition** (optional, default: `3`):

How long the fade should take in seconds (supports decimals, e.g., `0.5` for
500ms)

### **Brightness parameters** (optional):

Either **`brightness_pct`** (0-100) or **`brightness`** (0-255). A value of zero
means `off`

### **Color or color temperature parameters** (optional):

Only one target color or color temperature parameter allowed.

Either:

- **`color_temp_kelvin`**: Target color temperature in Kelvin (1000-40000)

or one of:

- **`hs_color`**: Target color as `[hue, saturation]` where hue is 0-360 and
    saturation is 0-100
- **`rgb_color`**: Target color as `[red, green, blue]` (0-255 each)
- **`rgbw_color`**: Target color as `[red, green, blue, white]` (0-255 each)
- **`rgbww_color`**: Target color as
    `[red, green, blue, cold_white, warm_white]` (0-255 each)
- **`xy_color`**: Target color as `[x, y]` (0-1 each)

The color parameters are converted to hue-saturation which are used internally,
while the `color_temp_kelvin` parameter is converted to `color_temp_mireds`
internally.

### **Starting values** (optional `from:` block):

You can specify starting values to override the current light state:

- **`from.brightness_pct`**: Starting brightness percentage
- **`from.color_temp_kelvin`**: Starting color temperature
- **`from.hs_color`**, **`from.rgb_color`**, etc.: Starting color (same formats
    as target colors)

### **Easing curves** (optional, default `Auto`):

Changing the brightness from 100 to 101 is a 1% change, but changing from 1 to 2
is a 100% change. This means that brightness changes are more jarring the lower
the brightness level. Fado tries to make fading smoother by supporting easing
curves:

- **`auto`** (default): Uses `ease_in_quad` when start brightness is less than
    end brightness, and `ease_out_quad` when end brightness is less than start
    brightness
- **`linear`**: Fades in a straight line
- **`ease_in_quad`**: Starts slow
- **`ease_in_cubic`**: Starts slower
- **`ease_out_quad`**: Ends slow
- **`ease_out_cubic`**: Ends slower
- **`ease_in_out_sine`**: Smooth S curve

### **State filter** (optional `only_if:`, default: none):

Restrict the fade to lights that are currently in a given state:

- **`on`**: only fade lights that are already on (skip lights that are off)
- **`off`**: only fade lights that are currently off (skip lights that are on)

Leave unset (the default) to fade every targeted light. Lights in any other
state (e.g. `unavailable`, `unknown`) are skipped whenever `only_if` is set.

!!! note

    In YAML, bare `on`/`off` parse as booleans, but Fado accepts them
    anyway — `only_if: on` and `only_if: "on"` are equivalent.

## Examples

### **Basic fade:**

```yaml
action: fado.fade_lights
target:
  entity_id: light.bedroom
data:
  brightness_pct: 50
  transition: 5
```

### **Dim only the lights that are already on:**

```yaml
action: fado.fade_lights
target:
  area_id: living_room
data:
  brightness_pct: 20
  transition: 5
  only_if: on
```

### **Fade multiple lights using different targets:**

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

### **Fade color temperature (warm to cool white) with specified starting point:**

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

### **Fade to a specific color:**

```yaml
action: fado.fade_lights
target:
  entity_id: light.accent
data:
  hs_color: [240, 100] # Blue
  brightness_pct: 80
  transition: 5
```

### **Automation Example**

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
