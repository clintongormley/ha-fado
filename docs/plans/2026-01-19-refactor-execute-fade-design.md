# Refactor \_execute_fade Design

## Goal

Break down the long `_execute_fade()` function (~200 lines) into smaller, semantically meaningful helper functions to improve readability.

## New Helper Functions

### 1. `_calculate_fade_steps()`

Pure function that calculates fade step parameters.

```python
def _calculate_fade_steps(
    start_level: int,
    end_level: int,
    transition_ms: int,
    min_step_delay_ms: int,
) -> tuple[int, int, float]:
    """Calculate fade step parameters.

    Returns:
        Tuple of (num_steps, delta_per_step, delay_ms_per_step)
    """
```

### 2. `_calculate_next_brightness()`

Pure function that calculates the next brightness level for a fade step.

```python
def _calculate_next_brightness(
    current_level: int,
    end_level: int,
    delta: int,
    is_last_step: bool,
) -> int:
    """Calculate the next brightness level for a fade step.

    Handles clamping, final step targeting, and the brightness=1 edge case.
    """
```

### 3. `_track_expected_brightness()`

Updates the expected brightness set for manual intervention detection.

```python
def _track_expected_brightness(entity_id: str, new_level: int, delta: int) -> None:
    """Track expected brightness for manual intervention detection.

    Maintains a set of the 2 most recent expected values.
    """
```

### 4. `_apply_brightness()`

Async function that calls the light service to set brightness.

```python
async def _apply_brightness(hass: HomeAssistant, entity_id: str, level: int) -> None:
    """Apply a brightness level to a light.

    Handles the special case of level 0 (turn off) vs positive levels (turn on).
    """
```

### 5. `_sleep_remaining_step_time()`

Async function that handles step timing.

```python
async def _sleep_remaining_step_time(step_start: float, delay_ms: float) -> None:
    """Sleep for the remaining time in a fade step.

    Subtracts elapsed time from target delay to maintain consistent fade duration.
    """
```

### 6. `_finalize_fade()`

Async function that handles successful fade completion.

```python
async def _finalize_fade(
    hass: HomeAssistant,
    entity_id: str,
    end_level: int,
    cancel_event: asyncio.Event,
) -> None:
    """Store final brightness after successful fade completion."""
```

## Refactored `_execute_fade()`

The main function becomes a clean orchestrator:

```python
async def _execute_fade(
    hass: HomeAssistant,
    entity_id: str,
    brightness_pct: int,
    transition_ms: int,
    min_step_delay_ms: int,
    cancel_event: asyncio.Event,
) -> None:
    """Execute the fade operation."""
    state = hass.states.get(entity_id)
    if not state:
        _LOGGER.warning("Entity %s not found", entity_id)
        return

    # Handle non-dimmable lights
    if ColorMode.BRIGHTNESS not in state.attributes.get(ATTR_SUPPORTED_COLOR_MODES, []):
        await _apply_brightness(hass, entity_id, 255 if brightness_pct > 0 else 0)
        return

    brightness = state.attributes.get(ATTR_BRIGHTNESS)
    start_level = int(brightness) if brightness is not None else 0
    end_level = int(brightness_pct / 100 * 255)

    if start_level == end_level:
        return

    # Store original brightness if not already stored
    existing_orig = _get_orig_brightness(hass, entity_id)
    if existing_orig == 0 and start_level > 0:
        _store_orig_brightness(hass, entity_id, start_level)

    # Initialize expected brightness tracking
    FADE_EXPECTED_BRIGHTNESS[entity_id] = {start_level}
    current_level = start_level

    # Calculate fade parameters
    num_steps, delta, delay_ms = _calculate_fade_steps(
        start_level, end_level, transition_ms, min_step_delay_ms
    )

    _LOGGER.debug(
        "Fading %s from %s to %s in %s steps", entity_id, start_level, end_level, num_steps
    )

    # Execute fade loop
    for i in range(num_steps):
        step_start = time.monotonic()

        if cancel_event.is_set():
            return

        current_level = _calculate_next_brightness(
            current_level, end_level, delta, is_last_step=(i == num_steps - 1)
        )
        _track_expected_brightness(entity_id, current_level, delta)

        await _apply_brightness(hass, entity_id, current_level)

        if cancel_event.is_set():
            return

        await _sleep_remaining_step_time(step_start, delay_ms)

    await _finalize_fade(hass, entity_id, end_level, cancel_event)
```

## Benefits

- **Reduced complexity**: ~80 lines down from ~200
- **Single responsibility**: Each helper does one thing
- **Testability**: Pure functions can be unit tested in isolation
- **Readability**: Flow is clear top-to-bottom with semantic function names

## Testing

Existing tests should continue to pass since behavior is unchanged. The refactor is purely structural.