"""Lovelace resource registration for the Fado card and dashboard strategy.

The Fado card (``fado-card``) and dashboard strategy (``ll-strategy-dashboard-fado``)
must be registered as Lovelace *resources* rather than loaded via
``frontend.add_extra_js_url``. add_extra_js_url injects the module into the index
``<script type="module">``, which runs before Home Assistant lazily installs
``@webcomponents/scoped-custom-element-registry`` (on first Lovelace render).
Installing that polyfill swaps ``window.customElements`` for a fresh registry,
dropping any element defined beforehand — so the card fails to resolve
("Configuration error: custom element doesn't exist") on a cold/hard load while
working after a soft refresh. Lovelace resources are imported during Lovelace
init, after the swap, so the element registers in the registry HA actually
queries.

Falls back to ``add_extra_js_url`` when the resource collection is unavailable
(e.g. Lovelace in YAML mode), which still works for the running session. The
panel (registered via ``panel_custom``) is unaffected — HA imports it after the
swap — so only the card and strategy need this treatment.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Tracks created resource IDs (keyed by storage_key) so they can be removed on
# unload. Kept separate from hass.data[DOMAIN], which holds the coordinator.
_RESOURCE_DATA_KEY = "fado_resource_ids"

# storage_key values for the two resources Fado ships.
CARD_RESOURCE_KEY = "card_resource_id"
STRATEGY_RESOURCE_KEY = "strategy_resource_id"


def _get_resources(hass: HomeAssistant) -> Any | None:
    """Return the Lovelace resource collection if it supports mutation."""
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is not None and hasattr(resources, "async_create_item"):
        return resources
    return None


async def async_register_card_resource(
    hass: HomeAssistant,
    base_url: str,
    card_url: str,
    storage_key: str,
) -> None:
    """Register a JS module as a Lovelace resource (idempotent).

    ``base_url`` is the path without any cache-bust query; ``card_url`` is the
    (possibly versioned) URL actually registered. An existing resource for the
    same ``base_url`` is updated to ``card_url`` so a rebuilt bundle is picked
    up. ``storage_key`` distinguishes this resource (card vs strategy) when
    recording its ID for later removal. Falls back to ``add_extra_js_url`` when
    the resource collection is unavailable.
    """
    try:
        resources = _get_resources(hass)
        if resources is not None:
            if not resources.loaded:
                await resources.async_load()
                resources.loaded = True
            for item in resources.async_items():
                url = item.get("url", "")
                if url == card_url:
                    hass.data.setdefault(_RESOURCE_DATA_KEY, {})[storage_key] = item["id"]
                    return  # Already the current version.
                if url.startswith(base_url):
                    await resources.async_update_item(item["id"], {"url": card_url})
                    hass.data.setdefault(_RESOURCE_DATA_KEY, {})[storage_key] = item["id"]
                    return
            item = await resources.async_create_item({"res_type": "module", "url": card_url})
            hass.data.setdefault(_RESOURCE_DATA_KEY, {})[storage_key] = item["id"]
            return
    except Exception:  # noqa: BLE001 — resource API is best-effort; fall back below.
        _LOGGER.debug(
            "Could not register %s as a Lovelace resource; falling back to add_extra_js_url",
            base_url,
            exc_info=True,
        )

    # Defensively initialise the extra-module-url store: the frontend component
    # creates it during its own setup, but it may be absent in minimal contexts
    # (e.g. tests), where add_extra_js_url would otherwise raise KeyError.
    hass.data.setdefault(frontend.DATA_EXTRA_MODULE_URL, set())  # type: ignore[arg-type]
    frontend.add_extra_js_url(hass, card_url)


async def async_unregister_card_resource(
    hass: HomeAssistant,
    card_url: str,
    storage_key: str,
) -> None:
    """Remove a previously registered resource (or its extra-js fallback)."""
    resource_id = hass.data.get(_RESOURCE_DATA_KEY, {}).pop(storage_key, None)
    if resource_id is None:
        try:
            frontend.remove_extra_js_url(hass, card_url)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not remove extra-js url %s", card_url, exc_info=True)
        return

    resources = _get_resources(hass)
    if resources is not None and hasattr(resources, "async_delete_item"):
        try:
            await resources.async_delete_item(resource_id)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not remove Lovelace resource %s", resource_id, exc_info=True)
