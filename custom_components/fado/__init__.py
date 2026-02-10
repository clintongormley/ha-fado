"""The Fado integration."""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    TrackStates,
    async_track_state_change_filtered,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EASING,
    ATTR_FROM,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MIN_STEP_DELAY_MS,
    DOMAIN,
    EVENT_CONFIG_UPDATED,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    OPTION_LOG_LEVEL,
    OPTION_MIN_STEP_DELAY_MS,
    SERVICE_EXCLUDE_LIGHTS,
    SERVICE_FADE_LIGHTS,
    SERVICE_INCLUDE_LIGHTS,
    STORAGE_KEY,
    UNCONFIGURED_CHECK_INTERVAL_HOURS,
    VALID_EASING,
)
from .coordinator import FadeCoordinator
from .notifications import _notify_unconfigured_lights
from .websocket_api import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# Service Schema
# =============================================================================

# Shared validators for reuse in main and from: schemas
_BRIGHTNESS_PCT = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
_BRIGHTNESS_RAW = vol.All(vol.Coerce(int), vol.Range(min=1, max=255))
_HS_COLOR = vol.ExactSequence(
    [
        vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
    ]
)
_RGB_CHANNEL = vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
_RGB_COLOR = vol.ExactSequence([_RGB_CHANNEL] * 3)
_RGBW_COLOR = vol.ExactSequence([_RGB_CHANNEL] * 4)
_RGBWW_COLOR = vol.ExactSequence([_RGB_CHANNEL] * 5)
_XY_COLOR = vol.ExactSequence(
    [
        vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
    ]
)
_COLOR_TEMP_KELVIN = vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000))

# Schema for the from: parameter (starting values)
_FROM_SCHEMA = vol.Schema(
    {
        vol.Exclusive(ATTR_BRIGHTNESS_PCT, "brightness"): _BRIGHTNESS_PCT,
        vol.Exclusive(ATTR_BRIGHTNESS, "brightness"): _BRIGHTNESS_RAW,
        vol.Exclusive(ATTR_HS_COLOR, "color"): _HS_COLOR,
        vol.Exclusive(ATTR_RGB_COLOR, "color"): _RGB_COLOR,
        vol.Exclusive(ATTR_RGBW_COLOR, "color"): _RGBW_COLOR,
        vol.Exclusive(ATTR_RGBWW_COLOR, "color"): _RGBWW_COLOR,
        vol.Exclusive(ATTR_XY_COLOR, "color"): _XY_COLOR,
        vol.Exclusive(ATTR_COLOR_TEMP_KELVIN, "color"): _COLOR_TEMP_KELVIN,
    }
)

# Full service schema (replaces the minimal ALLOW_EXTRA schema)
FADE_LIGHTS_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Exclusive(ATTR_BRIGHTNESS_PCT, "brightness"): _BRIGHTNESS_PCT,
        vol.Exclusive(ATTR_BRIGHTNESS, "brightness"): _BRIGHTNESS_RAW,
        vol.Optional(ATTR_TRANSITION): vol.All(vol.Coerce(float), vol.Range(min=0, max=3600)),
        vol.Optional(ATTR_EASING, default="auto"): vol.In(VALID_EASING),
        vol.Exclusive(ATTR_HS_COLOR, "color"): _HS_COLOR,
        vol.Exclusive(ATTR_RGB_COLOR, "color"): _RGB_COLOR,
        vol.Exclusive(ATTR_RGBW_COLOR, "color"): _RGBW_COLOR,
        vol.Exclusive(ATTR_RGBWW_COLOR, "color"): _RGBWW_COLOR,
        vol.Exclusive(ATTR_XY_COLOR, "color"): _XY_COLOR,
        vol.Exclusive(ATTR_COLOR_TEMP_KELVIN, "color"): _COLOR_TEMP_KELVIN,
        vol.Optional(ATTR_FROM): _FROM_SCHEMA,
    }
)


# =============================================================================
# Integration Setup
# =============================================================================


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Fado component."""
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"})
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fado from a config entry."""
    store: Store[dict[str, int]] = Store(hass, 1, STORAGE_KEY)
    min_step_delay_ms = entry.options.get(OPTION_MIN_STEP_DELAY_MS, DEFAULT_MIN_STEP_DELAY_MS)

    coordinator = FadeCoordinator(
        hass=hass,
        store=store,
        min_step_delay_ms=min_step_delay_ms,
    )
    await coordinator.async_load()

    hass.data[DOMAIN] = coordinator

    async def handle_fade_lights(call: ServiceCall) -> None:
        """Service handler wrapper."""
        await coordinator.handle_fade_lights(call)

    async def handle_exclude_lights(call: ServiceCall) -> None:
        """Exclude targeted lights from Fado."""
        entity_ids = coordinator.resolve_target_entity_ids(call)
        if entity_ids:
            await coordinator.set_exclude(entity_ids, exclude=True)

    async def handle_include_lights(call: ServiceCall) -> None:
        """Re-include targeted lights in Fado."""
        entity_ids = coordinator.resolve_target_entity_ids(call)
        if entity_ids:
            await coordinator.set_exclude(entity_ids, exclude=False)

    @callback
    def handle_light_state_change(event: Event[EventStateChangedData]) -> None:
        """Event handler wrapper."""
        coordinator.handle_state_change(event)

    hass.services.async_register(
        DOMAIN,
        SERVICE_FADE_LIGHTS,
        handle_fade_lights,
        schema=FADE_LIGHTS_SCHEMA,
    )

    target_only_schema = cv.make_entity_service_schema({})
    hass.services.async_register(
        DOMAIN, SERVICE_EXCLUDE_LIGHTS, handle_exclude_lights, schema=target_only_schema
    )
    hass.services.async_register(
        DOMAIN, SERVICE_INCLUDE_LIGHTS, handle_include_lights, schema=target_only_schema
    )

    # Track only light domain state changes (more efficient than listening to all events)
    tracker = async_track_state_change_filtered(
        hass,
        TrackStates(False, set(), {LIGHT_DOMAIN}),
        handle_light_state_change,
    )
    entry.async_on_unload(tracker.async_remove)

    # Listen for entity registry changes to clean up deleted entities and check for new ones
    async def handle_entity_registry_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Handle entity registry updates."""
        action = event.data["action"]
        entity_id = event.data["entity_id"]

        # Only handle light entities
        if not entity_id.startswith(f"{LIGHT_DOMAIN}."):
            return

        if action == "remove":
            await coordinator.cleanup_entity(entity_id)
            await _notify_unconfigured_lights(hass)
            hass.bus.async_fire(EVENT_CONFIG_UPDATED)
        elif action == "create":
            await _notify_unconfigured_lights(hass)
            hass.bus.async_fire(EVENT_CONFIG_UPDATED)
        elif action == "update":
            # Check if light was re-enabled (disabled_by changed)
            changes = event.data.get("changes", {})
            if "disabled_by" in changes:
                await _notify_unconfigured_lights(hass)
                hass.bus.async_fire(EVENT_CONFIG_UPDATED)

    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            handle_entity_registry_updated,
        )
    )

    # Register daily timer to check for unconfigured lights
    async def _daily_unconfigured_check(_now: datetime) -> None:
        """Daily check for unconfigured lights."""
        await _notify_unconfigured_lights(hass)

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _daily_unconfigured_check,
            timedelta(hours=UNCONFIGURED_CHECK_INTERVAL_HOURS),
        )
    )

    # Register WebSocket API
    async_register_websocket_api(hass)

    # Register panel (only if HTTP component is available - won't be in tests)
    if hass.http is not None:
        # Register static path for frontend files
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/fado_panel",
                    str(Path(__file__).parent / "frontend"),
                    cache_headers=False,  # Disable caching during development
                )
            ]
        )

        # Register the panel
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path="fado",
            webcomponent_name="fado-panel",
            sidebar_title="Fado",
            sidebar_icon="mdi:lightbulb-variant",
            module_url="/fado_panel/panel.js",
            require_admin=False,
        )

    # Apply stored log level on startup
    await _apply_stored_log_level(hass, entry)

    # Check for unconfigured lights and notify
    await _notify_unconfigured_lights(hass)

    # Prune stale storage after HA has fully started (all entities registered)
    async def _prune_on_start(_event: Event) -> None:
        await coordinator.async_prune_stale_storage()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _prune_on_start))

    return True


async def _apply_stored_log_level(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply the stored log level setting."""
    log_level = entry.options.get(OPTION_LOG_LEVEL, DEFAULT_LOG_LEVEL)

    # Map our level names to Python logging level names
    level_map = {
        LOG_LEVEL_WARNING: "warning",
        LOG_LEVEL_INFO: "info",
        LOG_LEVEL_DEBUG: "debug",
    }
    python_level = level_map.get(log_level, "warning")

    # Use HA's logger service to set the level
    # Logger service may not be available in tests
    with contextlib.suppress(Exception):
        await hass.services.async_call(
            "logger",
            "set_level",
            {f"custom_components.{DOMAIN}": python_level},
        )


async def async_unload_entry(hass: HomeAssistant, _entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: FadeCoordinator = hass.data[DOMAIN]
    await coordinator.shutdown()

    hass.services.async_remove(DOMAIN, SERVICE_FADE_LIGHTS)
    hass.services.async_remove(DOMAIN, SERVICE_EXCLUDE_LIGHTS)
    hass.services.async_remove(DOMAIN, SERVICE_INCLUDE_LIGHTS)
    hass.data.pop(DOMAIN, None)

    # Remove the panel
    frontend.async_remove_panel(hass, "fado")

    return True
