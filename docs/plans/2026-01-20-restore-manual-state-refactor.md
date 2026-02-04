# Refactor \_restore_manual_state

## Goal

Simplify `_restore_manual_state` for better readability by:

- Using a single integer to represent intended state (0 = OFF, >0 = ON at brightness)
- Extracting intent calculation to a helper function
- Reducing multiple exit points
- Clearer variable naming

## Helper Function

```python
def _get_intended_brightness(
    hass: HomeAssistant,
    entity_id: str,
    old_state,
    new_state,
) -> int | None:
    """Determine the intended brightness from a manual intervention.

    Returns:
        0: Light should be OFF
        >0: Light should be ON at this brightness
        None: Could not determine (integration unloaded)
    """
    if DOMAIN not in hass.data:
        return None

    new_brightness = new_state.attributes.get(ATTR_BRIGHTNESS)

    if new_state.state == STATE_OFF:
        return 0

    if old_state and old_state.state == STATE_OFF:
        # OFF -> ON: restore to original brightness
        orig = _get_orig_brightness(hass, entity_id)
        return orig if orig > 0 else new_brightness

    # ON -> ON: use the brightness from the event
    return new_brightness
```

## Refactored Main Function

```python
async def _restore_manual_state(
    hass: HomeAssistant,
    entity_id: str,
    old_state,
    new_state,
) -> None:
    """Restore intended state after manual intervention during fade.

    When manual intervention is detected during a fade, late fade events may
    overwrite the user's intended state. This function:
    1. Cancels the fade and waits for cleanup
    2. Compares current state to intended state
    3. Restores intended state if they differ

    The intended brightness encodes both state and brightness:
    - 0 means OFF
    - >0 means ON at that brightness
    """
    await _cancel_and_wait_for_fade(entity_id)

    intended = _get_intended_brightness(hass, entity_id, old_state, new_state)
    if intended is None:
        _clear_fade_interrupted(entity_id)
        return

    # Store as new original brightness (for future OFF->ON restore)
    if intended > 0:
        _store_orig_brightness(hass, entity_id, intended)

    # Get current state after fade cleanup
    current_state = hass.states.get(entity_id)
    if not current_state:
        _clear_fade_interrupted(entity_id)
        return

    current = current_state.attributes.get(ATTR_BRIGHTNESS) or 0
    if current_state.state == STATE_OFF:
        current = 0

    # Restore if current differs from intended
    if intended == 0 and current != 0:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    elif intended > 0 and current != intended:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: intended},
            blocking=True,
        )

    _clear_fade_interrupted(entity_id)
```

## Benefits

- Single integer comparison instead of separate on/off + brightness checks
- Helper function isolates the intent calculation logic
- Linear flow: cancel → get intended → get current → compare → restore → cleanup
- Single exit point for cleanup at the end
- `blocking=True` ensures state is updated before clearing the interrupted flag