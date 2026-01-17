# Brightness Tracking Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace single-value brightness storage with dual-value system (orig/curr) to properly restore user's intended brightness when lights are manually turned on.

**Architecture:** Event listener tracks context IDs to distinguish fade service changes from external changes. Fade function manages `curr` internally while event listener manages `orig` and handles manual interventions.

**Tech Stack:** Home Assistant custom integration, Python asyncio, Home Assistant storage API

---

## Task 1: Update Constants

**Files:**
- Modify: `custom_components/fade_lights/const.py`

**Step 1: Add new constants and bump storage version**

Replace the entire contents of `const.py` with:

```python
"""Constants for the Fade Lights integration."""

DOMAIN = "fade_lights"

# Services
SERVICE_FADE_LIGHTS = "fade_lights"

# Service attributes
ATTR_BRIGHTNESS_PCT = "brightness_pct"
ATTR_TRANSITION = "transition"

# Storage
STORAGE_KEY = f"{DOMAIN}.last_brightness"
STORAGE_VERSION = 2

# Storage keys
KEY_ORIG_BRIGHTNESS = "orig"
KEY_CURR_BRIGHTNESS = "curr"

# Option keys
OPTION_DEFAULT_BRIGHTNESS_PCT = "default_brightness_pct"
OPTION_DEFAULT_TRANSITION = "default_transition"
OPTION_STEP_DELAY_MS = "step_delay_ms"

# Defaults (used when options are not set)
DEFAULT_BRIGHTNESS_PCT = 40
DEFAULT_TRANSITION = 3  # seconds
DEFAULT_STEP_DELAY_MS = 100  # milliseconds
```

**Step 2: Verify file saved correctly**

Run: `cat custom_components/fade_lights/const.py`

**Step 3: Commit**

```bash
git add custom_components/fade_lights/const.py
git commit -m "refactor(const): update constants for dual-value storage

- Bump STORAGE_VERSION to 2
- Add KEY_ORIG_BRIGHTNESS and KEY_CURR_BRIGHTNESS
- Remove ATTR_FORCE, DEFAULT_FORCE
- Remove auto-brightness constants"
```

---

## Task 2: Update Config Flow

**Files:**
- Modify: `custom_components/fade_lights/config_flow.py`

**Step 1: Remove auto-brightness options**

Replace the entire contents of `config_flow.py` with:

```python
"""Config flow for Fade Lights integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    DEFAULT_BRIGHTNESS_PCT,
    DEFAULT_STEP_DELAY_MS,
    DEFAULT_TRANSITION,
    DOMAIN,
    OPTION_DEFAULT_BRIGHTNESS_PCT,
    OPTION_DEFAULT_TRANSITION,
    OPTION_STEP_DELAY_MS,
)


class FadeLightsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fade Lights."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow a single instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Create entry immediately without showing a form
        return self.async_create_entry(
            title="Fade Lights",
            data={},
        )

    async def async_step_import(
        self, import_config: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle import from configuration.yaml or auto-setup."""
        # Only allow a single instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="Fade Lights",
            data={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> FadeLightsOptionsFlow:
        """Get the options flow for this handler."""
        return FadeLightsOptionsFlow()


class FadeLightsOptionsFlow(OptionsFlow):
    """Handle options flow for Fade Lights."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        OPTION_DEFAULT_BRIGHTNESS_PCT,
                        default=options.get(
                            OPTION_DEFAULT_BRIGHTNESS_PCT, DEFAULT_BRIGHTNESS_PCT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                    vol.Optional(
                        OPTION_DEFAULT_TRANSITION,
                        default=options.get(OPTION_DEFAULT_TRANSITION, DEFAULT_TRANSITION),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                    vol.Optional(
                        OPTION_STEP_DELAY_MS,
                        default=options.get(OPTION_STEP_DELAY_MS, DEFAULT_STEP_DELAY_MS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=1000)),
                }
            ),
        )
```

**Step 2: Verify file saved correctly**

Run: `cat custom_components/fade_lights/config_flow.py`

**Step 3: Commit**

```bash
git add custom_components/fade_lights/config_flow.py
git commit -m "refactor(config_flow): remove auto-brightness options

Auto-brightness feature is no longer needed with proper
brightness tracking."
```

---

## Task 3: Update Strings and Translations

**Files:**
- Modify: `custom_components/fade_lights/strings.json`
- Modify: `custom_components/fade_lights/translations/en.json`

**Step 1: Update strings.json**

Replace the entire contents of `strings.json` with:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Set up Fade Lights",
        "description": "This integration provides smooth light fading with automatic brightness restoration."
      }
    },
    "abort": {
      "single_instance_allowed": "Only a single instance is allowed."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Configure fade lights",
        "description": "Customize how lights fade.",
        "data": {
          "default_brightness_pct": "Fade to brightness",
          "default_transition": "Transition time",
          "step_delay_ms": "Minimum delay between steps"
        },
        "data_description": {
          "default_brightness_pct": "Default brightness level if not specified in the action call (0-100%).",
          "default_transition": "Default time to transition to the new brightness level in seconds (0-3600, which is up to 1 hour).",
          "step_delay_ms": "The lower this value (in milliseconds), the shorter the pause between each brightness step change and thus the smoother the transition, but too low values may cause transitions to last longer than expected and put unnecessary load on Home Assistant. (Default 100ms)"
        }
      }
    }
  },
  "services": {
    "fade_lights": {
      "name": "Fade lights",
      "description": "Fades lights to a desired level over a specified transition period.",
      "fields": {
        "entity_id": {
          "name": "Entity ID",
          "description": "Entity ID of a light or light group."
        },
        "brightness_pct": {
          "name": "Brightness percentage",
          "description": "Integer value from 0 to 100 representing the desired final brightness level as a percentage (default 40)."
        },
        "transition": {
          "name": "Transition time",
          "description": "Transition time for fading indicated in seconds (default 3)."
        }
      }
    }
  }
}
```

**Step 2: Update translations/en.json**

Replace the entire contents of `translations/en.json` with:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Set up Fade Lights",
        "description": "This integration provides smooth light fading with automatic brightness restoration."
      }
    },
    "abort": {
      "single_instance_allowed": "Only a single instance is allowed."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Configure fade lights",
        "description": "Customize how lights fade.",
        "data": {
          "default_brightness_pct": "Fade to brightness",
          "default_transition": "Transition time",
          "step_delay_ms": "Minimum delay between steps"
        },
        "data_description": {
          "default_brightness_pct": "Default brightness level if not specified in the action call (0-100%).",
          "default_transition": "Default time to transition to the new brightness level in seconds (0-3600, which is up to 1 hour).",
          "step_delay_ms": "The lower this value (in milliseconds), the shorter the pause between each brightness step change and thus the smoother the transition, but too low values may cause transitions to last longer than expected and put unnecessary load on Home Assistant. (Default 100ms)"
        }
      }
    }
  },
  "services": {
    "fade_lights": {
      "name": "Fade lights",
      "description": "Fades lights to a desired level over a specified transition period.",
      "fields": {
        "entity_id": {
          "name": "Entity ID",
          "description": "Entity ID of a light or light group."
        },
        "brightness_pct": {
          "name": "Brightness percentage",
          "description": "Integer value from 0 to 100 representing the desired final brightness level as a percentage (default 40)."
        },
        "transition": {
          "name": "Transition time",
          "description": "Transition time for fading indicated in seconds (default 3)."
        }
      }
    }
  }
}
```

**Step 3: Commit**

```bash
git add custom_components/fade_lights/strings.json custom_components/fade_lights/translations/en.json
git commit -m "refactor(strings): remove auto-brightness and force translations"
```

---

## Task 4: Update services.yaml

**Files:**
- Modify: `custom_components/fade_lights/services.yaml`

**Step 1: Remove force parameter**

Replace the entire contents of `services.yaml` with:

```yaml
fade_lights:
  name: Fade lights
  description: Fades lights to a desired level over a specified transition period.
  fields:
    entity_id:
      name: Entity ID
      description: Entity ID of a light or light group.
      required: true
      example: "light.bedroom"
      selector:
        entity:
          domain: light
          multiple: true
    brightness_pct:
      name: Brightness percentage
      description: Integer value from 0 to 100 representing the desired final brightness level as a percentage.
      required: false
      default: 40
      example: 75
      selector:
        number:
          min: 0
          max: 100
          mode: slider
          unit_of_measurement: "%"
    transition:
      name: Transition time
      description: Transition time for fading indicated in seconds.
      required: false
      default: 3
      example: "3"
      selector:
        text:
```

**Step 2: Commit**

```bash
git add custom_components/fade_lights/services.yaml
git commit -m "refactor(services): remove force parameter"
```

---

## Task 5: Rewrite Main Integration

**Files:**
- Modify: `custom_components/fade_lights/__init__.py`

**Step 1: Replace entire __init__.py**

Replace the entire contents of `__init__.py` with:

```python
"""The Fade Lights integration."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.light.const import ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_STATE_CHANGED,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import (
    Context,
    Event,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
    DEFAULT_BRIGHTNESS_PCT,
    DEFAULT_STEP_DELAY_MS,
    DEFAULT_TRANSITION,
    DOMAIN,
    KEY_CURR_BRIGHTNESS,
    KEY_ORIG_BRIGHTNESS,
    OPTION_DEFAULT_BRIGHTNESS_PCT,
    OPTION_DEFAULT_TRANSITION,
    OPTION_STEP_DELAY_MS,
    SERVICE_FADE_LIGHTS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Track active fade tasks
ACTIVE_FADES: dict[str, asyncio.Task] = {}

# Track contexts created by this integration
ACTIVE_CONTEXTS: set[str] = set()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Fade Lights component."""
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"})
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fade Lights from a config entry."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    storage_data = await store.async_load() or {}

    # Migrate from v1 to v2 storage format
    storage_data = _migrate_storage(storage_data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = {
        "store": store,
        "data": storage_data,
    }

    default_brightness = entry.options.get(
        OPTION_DEFAULT_BRIGHTNESS_PCT, DEFAULT_BRIGHTNESS_PCT
    )
    default_transition = entry.options.get(
        OPTION_DEFAULT_TRANSITION, DEFAULT_TRANSITION
    )
    step_delay_ms = entry.options.get(OPTION_STEP_DELAY_MS, DEFAULT_STEP_DELAY_MS)

    async def handle_fade_lights(call: ServiceCall) -> None:
        """Handle the fade_lights service call."""
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        brightness_pct = call.data.get(ATTR_BRIGHTNESS_PCT, default_brightness)
        transition = call.data.get(ATTR_TRANSITION, default_transition)

        if isinstance(entity_ids, str):
            entity_ids = [e.strip() for e in entity_ids.split(",")]

        expanded_entities = await _expand_entity_ids(hass, entity_ids)

        _LOGGER.debug("Fading lights: %s", expanded_entities)

        transition_ms = transition * 1000
        _LOGGER.debug("Transition in ms: %s", transition_ms)

        # Create a context for this fade operation
        context = Context()
        ACTIVE_CONTEXTS.add(context.id)

        try:
            tasks = [
                asyncio.create_task(
                    _fade_light(
                        hass,
                        entity_id,
                        brightness_pct,
                        transition_ms,
                        context,
                        step_delay_ms,
                    )
                )
                for entity_id in expanded_entities
            ]

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            ACTIVE_CONTEXTS.discard(context.id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_FADE_LIGHTS,
        handle_fade_lights,
        schema=None,
    )

    @callback
    def handle_light_state_change(event: Event) -> None:
        """Handle all light state changes."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state:
            return

        entity_id = new_state.entity_id

        if not entity_id.startswith("light."):
            return

        # Ignore changes from our own fade operations
        if event.context.id in ACTIVE_CONTEXTS:
            return

        # Ignore group helpers
        if new_state.attributes.get(ATTR_ENTITY_ID) is not None:
            return

        # Light turned ON (was OFF)
        if old_state and old_state.state == STATE_OFF and new_state.state == STATE_ON:
            # Check if light supports brightness
            if ColorMode.BRIGHTNESS not in new_state.attributes.get(
                ATTR_SUPPORTED_COLOR_MODES, []
            ):
                return

            orig_brightness = _get_orig_brightness(hass, entity_id)
            if orig_brightness > 0:
                current_brightness = new_state.attributes.get(ATTR_BRIGHTNESS, 0)
                if current_brightness != orig_brightness:
                    _LOGGER.debug(
                        "Restoring %s to original brightness %s",
                        entity_id,
                        orig_brightness,
                    )
                    hass.async_create_task(
                        hass.services.async_call(
                            LIGHT_DOMAIN,
                            SERVICE_TURN_ON,
                            {
                                ATTR_ENTITY_ID: entity_id,
                                ATTR_BRIGHTNESS: orig_brightness,
                            },
                        )
                    )
            return

        # Light turned OFF - no action needed
        if new_state.state == STATE_OFF:
            return

        # Brightness changed while light was already ON
        if old_state and old_state.state == STATE_ON and new_state.state == STATE_ON:
            new_brightness = new_state.attributes.get(ATTR_BRIGHTNESS)
            old_brightness = old_state.attributes.get(ATTR_BRIGHTNESS)

            if new_brightness != old_brightness and new_brightness is not None:
                # Cancel active fade if any
                if entity_id in ACTIVE_FADES:
                    _LOGGER.debug(
                        "Cancelling fade on %s due to manual brightness change",
                        entity_id,
                    )
                    ACTIVE_FADES[entity_id].cancel()

                # Store new brightness as original
                _LOGGER.debug(
                    "Storing manual brightness change for %s: %s",
                    entity_id,
                    new_brightness,
                )
                _store_orig_brightness(hass, entity_id, new_brightness)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_STATE_CHANGED, handle_light_state_change)
    )
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for task in ACTIVE_FADES.values():
        task.cancel()
    ACTIVE_FADES.clear()
    ACTIVE_CONTEXTS.clear()

    hass.services.async_remove(DOMAIN, SERVICE_FADE_LIGHTS)
    hass.data.pop(DOMAIN, None)

    return True


def _migrate_storage(storage_data: dict) -> dict:
    """Migrate storage from v1 to v2 format."""
    migrated = {}
    for key, value in storage_data.items():
        if isinstance(value, int):
            # v1 format: single integer
            migrated[key] = {
                KEY_ORIG_BRIGHTNESS: value,
                KEY_CURR_BRIGHTNESS: value,
            }
        elif isinstance(value, dict):
            # Already v2 format
            migrated[key] = value
        else:
            # Unknown format, skip
            _LOGGER.warning("Unknown storage format for %s: %s", key, value)
    return migrated


async def _fade_light(
    hass: HomeAssistant,
    entity_id: str,
    brightness_pct: int,
    transition_ms: int,
    context: Context,
    step_delay_ms: int,
) -> None:
    """Fade a single light to the specified brightness."""
    if entity_id in ACTIVE_FADES:
        ACTIVE_FADES[entity_id].cancel()
        try:
            await ACTIVE_FADES[entity_id]
        except asyncio.CancelledError:
            pass

    current_task = asyncio.current_task()
    if current_task:
        ACTIVE_FADES[entity_id] = current_task

    try:
        await _execute_fade(
            hass, entity_id, brightness_pct, transition_ms, context, step_delay_ms
        )
    except asyncio.CancelledError:
        _LOGGER.debug("Fade cancelled for %s", entity_id)
    finally:
        ACTIVE_FADES.pop(entity_id, None)


async def _execute_fade(
    hass: HomeAssistant,
    entity_id: str,
    brightness_pct: int,
    transition_ms: int,
    context: Context,
    step_delay_ms: int,
) -> None:
    """Execute the fade operation."""
    state = hass.states.get(entity_id)
    if not state:
        _LOGGER.warning("Entity %s not found", entity_id)
        return

    # Handle non-dimmable lights
    if ColorMode.BRIGHTNESS not in state.attributes.get(ATTR_SUPPORTED_COLOR_MODES, []):
        if brightness_pct == 0:
            _LOGGER.debug("Turning off non-dimmable light %s", entity_id)
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity_id},
                context=context,
                blocking=True,
            )
        else:
            _LOGGER.debug("Turning on non-dimmable light %s", entity_id)
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                context=context,
                blocking=True,
            )
        return

    start_level = _get_current_level(hass, entity_id)
    end_level = int(brightness_pct / 100 * 255)

    _LOGGER.debug(
        "Fading %s from %s to %s in %sms",
        entity_id,
        start_level,
        end_level,
        transition_ms,
    )

    if start_level == end_level:
        _LOGGER.debug("Already at target brightness for %s", entity_id)
        return

    # Store starting brightness as curr
    _store_curr_brightness(hass, entity_id, start_level)

    # Calculate steps
    level_diff = abs(end_level - start_level)
    delay_ms = round(transition_ms / level_diff) if level_diff > 0 else step_delay_ms
    delay_ms = max(delay_ms, step_delay_ms)

    num_steps = math.ceil(transition_ms / (delay_ms + 30)) or 1
    delta = (end_level - start_level) / num_steps
    delta = math.ceil(delta) if delta > 0 else math.floor(delta)

    _LOGGER.debug(
        "Fading in %s steps of delta %s with delay %sms",
        num_steps,
        delta,
        delay_ms,
    )

    for i in range(num_steps):
        curr = _get_curr_brightness(hass, entity_id)
        new_level = curr + delta
        new_level = max(0, min(255, new_level))

        # Ensure we hit the target on the last step
        if (delta > 0 and new_level > end_level) or (delta < 0 and new_level < end_level):
            new_level = end_level

        if i == num_steps - 1:
            new_level = end_level

        # Handle brightness level 1 edge case
        if new_level == 1:
            new_level = 0 if delta < 0 else 2

        _store_curr_brightness(hass, entity_id, new_level)

        if new_level == 0:
            _LOGGER.debug("Step %s: Turning off %s", i, entity_id)
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity_id},
                context=context,
                blocking=True,
            )
        else:
            _LOGGER.debug("Step %s: Setting %s to %s", i, entity_id, new_level)
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_ON,
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_BRIGHTNESS: int(new_level),
                },
                context=context,
                blocking=True,
            )

        await asyncio.sleep(delay_ms / 1000)

    # Store orig brightness if we faded to a non-zero value
    if end_level > 0:
        _store_orig_brightness(hass, entity_id, end_level)
        await _save_storage(hass)

    _LOGGER.debug("Fade complete for %s", entity_id)


def _get_current_level(hass: HomeAssistant, entity_id: str) -> int:
    """Get current brightness level from the light entity."""
    state = hass.states.get(entity_id)
    if not state:
        return 0
    brightness = state.attributes.get(ATTR_BRIGHTNESS)
    if brightness is None:
        return 0
    return int(brightness)


def _get_storage_key(entity_id: str) -> str:
    """Get storage key for an entity."""
    return entity_id.replace(".", "_")


def _get_orig_brightness(hass: HomeAssistant, entity_id: str) -> int:
    """Get stored original brightness for an entity."""
    key = _get_storage_key(entity_id)
    storage_data = hass.data.get(DOMAIN, {}).get("data", {})
    entity_data = storage_data.get(key, {})
    return entity_data.get(KEY_ORIG_BRIGHTNESS, 0)


def _get_curr_brightness(hass: HomeAssistant, entity_id: str) -> int:
    """Get stored current brightness for an entity."""
    key = _get_storage_key(entity_id)
    storage_data = hass.data.get(DOMAIN, {}).get("data", {})
    entity_data = storage_data.get(key, {})
    return entity_data.get(KEY_CURR_BRIGHTNESS, 0)


def _store_orig_brightness(hass: HomeAssistant, entity_id: str, level: int) -> None:
    """Store original brightness for an entity."""
    key = _get_storage_key(entity_id)
    storage_data = hass.data[DOMAIN]["data"]
    if key not in storage_data:
        storage_data[key] = {}
    storage_data[key][KEY_ORIG_BRIGHTNESS] = level


def _store_curr_brightness(hass: HomeAssistant, entity_id: str, level: int) -> None:
    """Store current brightness for an entity."""
    key = _get_storage_key(entity_id)
    storage_data = hass.data[DOMAIN]["data"]
    if key not in storage_data:
        storage_data[key] = {}
    storage_data[key][KEY_CURR_BRIGHTNESS] = level


async def _save_storage(hass: HomeAssistant) -> None:
    """Save storage data to disk."""
    store: Store = hass.data[DOMAIN]["store"]
    await store.async_save(hass.data[DOMAIN]["data"])


async def _expand_entity_ids(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Expand light groups recursively."""
    result = []
    _LOGGER.debug("Expanding entity IDs: %s", entity_ids)

    for entity_id in entity_ids:
        if not entity_id.startswith("light."):
            raise ServiceValidationError(f"Entity '{entity_id}' is not a light")

        state = hass.states.get(entity_id)
        if state is None:
            _LOGGER.error("Unknown light '%s'", entity_id)
            continue

        if ATTR_ENTITY_ID in state.attributes:
            group_entities = state.attributes[ATTR_ENTITY_ID]
            if isinstance(group_entities, str):
                group_entities = [group_entities]
            result.extend(await _expand_entity_ids(hass, group_entities))
        else:
            result.append(entity_id)

    return list(set(result))
```

**Step 2: Verify file saved correctly**

Run: `head -100 custom_components/fade_lights/__init__.py`

**Step 3: Run linting**

Run: `cd /tmp/ha_fade_lights && ruff check custom_components/fade_lights/`

Expected: All checks passed!

**Step 4: Commit**

```bash
git add custom_components/fade_lights/__init__.py
git commit -m "feat: implement dual-value brightness tracking

- Add ACTIVE_CONTEXTS to track fade service context IDs
- Replace single-value storage with orig/curr dual-value system
- Add event listener to detect manual brightness changes
- Restore original brightness when light manually turned on
- Cancel active fade when manual intervention detected
- Add storage migration from v1 to v2 format
- Remove force parameter and _is_automated function
- Remove auto-brightness feature"
```

---

## Task 6: Update README

**Files:**
- Modify: `README.md`

**Step 1: Replace entire README.md**

Replace the entire contents of `README.md` with:

```markdown
# Fade Lights Custom Integration

A Home Assistant custom integration that provides smooth light fading with automatic brightness restoration.

## Features

### Smooth Light Fading Service

- Fade lights to any brightness level (0-100%) over a specified transition period
- Supports individual lights and light groups
- Automatically expands light groups
- Cancels fade when lights are manually adjusted

### Automatic Brightness Restoration

When you fade a light down to off and then manually turn it back on, the integration automatically restores the light to its original brightness (before the fade started).

**Example:**
1. Light is at 80% brightness
2. You fade it to 0% (off) over 30 minutes
3. Later, you turn the light on manually
4. Light automatically restores to 80%

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the 3 dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/clintongormley/ha_fade_lights` as an integration
5. Click "Explore & Download Repositories"
6. Search for "Fade Lights"
7. Click "Download"
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/fade_lights` folder to your Home Assistant installation:
   ```
   <config_directory>/custom_components/fade_lights/
   ```
2. Restart Home Assistant

## Configuration

After installation and restart, add the integration via the Home Assistant UI:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Fade Lights"
4. Click to add it

Once configured, the `fade_lights.fade_lights` service will be available in **Developer Tools** → **Actions**.

## Usage

### Service: `fade_lights.fade_lights`

Fades one or more lights to a target brightness over a transition period.

#### Parameters:

- **entity_id** (required): Light entity ID, light group, or list of light entities
- **brightness_pct** (optional, default: 40): Target brightness percentage (0-100)
- **transition** (optional, default: 3): Transition duration in seconds

#### Examples:

**Basic fade:**

```yaml
service: fade_lights.fade_lights
data:
  entity_id: light.bedroom
  brightness_pct: 50
  transition: 5
```

**Fade multiple lights:**

```yaml
service: fade_lights.fade_lights
data:
  entity_id:
    - light.bedroom
    - light.living_room
  brightness_pct: 80
  transition: 10
```

**Fade a light group:**

```yaml
service: fade_lights.fade_lights
data:
  entity_id: light.all_downstairs
  brightness_pct: 30
  transition: 60
```

### Automation Example

```yaml
automation:
  - alias: "Sunset fade"
    trigger:
      - platform: sun
        event: sunset
        offset: "-00:30:00"
    action:
      - service: fade_lights.fade_lights
        data:
          entity_id: light.living_room
          brightness_pct: 20
          transition: 1800 # 30 minutes
```

## How It Works

### Brightness Tracking

The integration maintains two brightness values for each light:
- **Original brightness**: The user's intended brightness level
- **Current brightness**: The brightness being set during fade operations

When you fade a light to off, the original brightness is preserved. When the light is manually turned on again, it's automatically restored to that original brightness.

### Manual Change Detection

The integration uses Home Assistant's context system to distinguish between:
- Changes made by the fade service (ignored for restoration)
- Changes made manually or by other automations (triggers brightness restoration)

If you manually adjust a light's brightness while it's on, that becomes the new "original" brightness.

### Non-Dimmable Lights

Lights that do not support brightness will turn off when brightness is set to 0, or turn on when brightness is greater than 0.

## License

MIT License - feel free to modify and redistribute
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for brightness tracking redesign

- Remove references to force parameter
- Remove auto-brightness feature documentation
- Add automatic brightness restoration documentation
- Update How It Works section"
```

---

## Task 7: Test the Integration

**Step 1: Copy to test directory**

```bash
cp -r /tmp/ha_fade_lights/custom_components/fade_lights /workspaces/homeassistant-core/config/custom_components/
```

**Step 2: Verify files copied**

Run: `ls -la /workspaces/homeassistant-core/config/custom_components/fade_lights/`

**Step 3: Manual testing checklist**

Test in Home Assistant:
1. Reload the integration
2. Fade a light from 80% to 0%
3. Manually turn the light on
4. Verify it restores to 80% (not 1%)
5. Manually change brightness to 50%
6. Fade to 0%
7. Manually turn on
8. Verify it restores to 50%

---

## Task 8: Push Changes

**Step 1: Push to remote**

```bash
cd /tmp/ha_fade_lights && git push
```

---

## Summary

This plan implements the brightness tracking redesign in 8 tasks:

1. Update constants (add storage keys, bump version, remove old constants)
2. Update config flow (remove auto-brightness options)
3. Update strings/translations (remove auto-brightness text)
4. Update services.yaml (remove force parameter)
5. Rewrite main integration (implement dual-value tracking)
6. Update README documentation
7. Test the integration
8. Push changes
