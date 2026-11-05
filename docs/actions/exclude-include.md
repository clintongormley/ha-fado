# `fado.exclude_lights` / `fado.include_lights`

Excludes one or more lights from Fado. Excluded lights are ignored by fade
operations and state tracking. On Home Assistant 2026.11 or newer, you can leave
a light out of a single fade instead with the target's `exclude` block,
described in [`fado.fade_lights`](fade-lights.md).

## Parameters

### **`target`** (required):

Specify which lights to include or exclude using any combination of:

- **`entity_id`**: One or more light entities (e.g., `light.bedroom`)
- **`device_id`**: One or more device IDs
- **`area_id`**: One or more area IDs (e.g., `living_room`)
- **`floor_id`**: One or more floor IDs
- **`label_id`**: One or more label IDs

Light groups from Home Assistant's Group integration are not expanded here.
Targeting one does not change its member lights: each stays excluded or included
as it was. To exclude or include its lights, target the lights themselves. An
old-style group (`group.upstairs`) works differently, because Home Assistant
expands it into its members before Fado sees it, so each member is treated as if
you had targeted it directly. Duplicate entities are automatically deduplicated.

## Examples

### Exclude lights

```yaml
action: fado.exclude_lights
target:
  entity_id: light.bedroom
```

### Include lights by area

```yaml
action: fado.include_lights
target:
  area_id:
    - kitchen
    - livingroom
```
