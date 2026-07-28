# `fado.exclude_lights` / `fado.include_lights`

Excludes one or more lights from Fado. Excluded lights are ignored by fade
operations and state tracking.

## Parameters

### **`target`** (required):

Specify which lights to include or exclude using any combination of:

- **`entity_id`**: One or more light entities (e.g., `light.bedroom`)
- **`device_id`**: One or more device IDs
- **`area_id`**: One or more area IDs (e.g., `living_room`)
- **`floor_id`**: One or more floor IDs
- **`label_id`**: One or more label IDs

Light groups are automatically expanded to their individual lights. Duplicate
entities are automatically deduplicated.

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
