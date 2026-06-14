"""Helpers for surfacing unconfigured lights as a Repairs issue.

("Notification" terminology is retained in some names/options for backward
compatibility; the surface itself is now the issue registry, not a persistent
notification.)
"""

from __future__ import annotations

from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import (
    DEFAULT_DASHBOARD_URL,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_SHOW_SIDEBAR,
    DOMAIN,
    LEGACY_NOTIFICATION_ID,
    OPTION_DASHBOARD_URL,
    OPTION_NOTIFICATIONS_ENABLED,
    OPTION_SHOW_SIDEBAR,
    REQUIRED_CONFIG_FIELDS,
    UNCONFIGURED_ISSUE_ID,
)
from .coordinator import FadeCoordinator


def _get_config_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Get the Fado config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _get_unconfigured_lights(hass: HomeAssistant) -> set[str]:
    """Return set of light entity_ids missing required configuration.

    A light is considered unconfigured if:
    - It is enabled (not disabled)
    - It is NOT a light group (has entity_id in state attributes)
    - It is NOT excluded (exclude: true in storage)
    - It is missing any required config field (currently just min_delay_ms)
    """
    coordinator: FadeCoordinator | None = hass.data.get(DOMAIN)
    if coordinator is None:
        return set()

    entity_registry = er.async_get(hass)
    storage_data = coordinator.data

    unconfigured = set()
    for entry in entity_registry.entities.values():
        # Only check lights
        if entry.domain != LIGHT_DOMAIN:
            continue

        # Skip disabled lights
        if entry.disabled:
            continue

        entity_id = entry.entity_id

        # Skip light groups (they have entity_id in state attributes)
        state = hass.states.get(entity_id)
        if state and "entity_id" in state.attributes:
            continue

        config = storage_data.get(entity_id, {})

        # Skip excluded lights
        if config.get("exclude", False):
            continue

        # Check if any required field is missing
        if not REQUIRED_CONFIG_FIELDS.issubset(config.keys()):
            unconfigured.add(entity_id)

    return unconfigured


def _get_notification_link_url(hass: HomeAssistant) -> str:
    """Get the URL to use in the repair issue's learn-more link.

    Returns the URL string, or empty string for no link.
    If sidebar is enabled, links to /fado. Otherwise uses the dashboard URL option.
    """
    entry = _get_config_entry(hass)
    if not entry:
        return "/fado"

    show_sidebar = entry.options.get(OPTION_SHOW_SIDEBAR, DEFAULT_SHOW_SIDEBAR)
    if show_sidebar:
        return "/fado"

    return entry.options.get(OPTION_DASHBOARD_URL, DEFAULT_DASHBOARD_URL)


def _issue_learn_more_url(hass: HomeAssistant) -> str | None:
    """Build the Repairs issue's learn-more URL from the configured link.

    A relative path is given the ``homeassistant://`` scheme so the Repairs
    dialog navigates in-app and closes (the frontend rewrites
    ``homeassistant://<path>`` -> ``/<path>``) instead of opening a new tab. An
    already-absolute URL (a user-configured full dashboard URL) is used as-is.
    No configured link yields ``None`` (the dialog shows no learn-more button).
    """
    link = _get_notification_link_url(hass)
    if not link:
        return None
    if "://" in link:
        return link
    return f"homeassistant://{link.lstrip('/')}"


async def _notify_unconfigured_lights(hass: HomeAssistant) -> None:
    """Check for unconfigured lights and create/clear the Repairs issue.

    If there are unconfigured lights, creates (or refreshes) a single aggregate
    issue in the issue registry with a count and a learn-more link to the Fado
    panel/dashboard. If all lights are configured — or notifications are
    disabled — deletes any existing issue.

    Skipped before HA has fully started because entity states (needed to detect
    light groups) are not yet available.
    """
    if hass.state is not CoreState.running:
        return

    entry = _get_config_entry(hass)
    if entry:
        notifications_enabled = entry.options.get(
            OPTION_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATIONS_ENABLED
        )
        if not notifications_enabled:
            ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)
            return

    unconfigured = _get_unconfigured_lights(hass)

    if unconfigured:
        ir.async_create_issue(
            hass,
            DOMAIN,
            UNCONFIGURED_ISSUE_ID,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=UNCONFIGURED_ISSUE_ID,
            translation_placeholders={"count": str(len(unconfigured))},
            learn_more_url=_issue_learn_more_url(hass),
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, UNCONFIGURED_ISSUE_ID)


def _dismiss_legacy_notification(hass: HomeAssistant) -> None:
    """Dismiss the pre-Repairs persistent notification (upgrade cleanup).

    Idempotent no-op once the notification is gone — kept so an in-place reload
    or entry removal after upgrade doesn't leave the old notification alongside
    the new issue.
    """
    from homeassistant.components import persistent_notification  # noqa: PLC0415

    persistent_notification.async_dismiss(hass, LEGACY_NOTIFICATION_ID)
