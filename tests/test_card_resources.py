"""Tests for Lovelace card/strategy resource registration.

These guard the cold-load fix: the card and strategy JS must be registered as
Lovelace *resources* (imported by HA after it swaps in the scoped custom-element
registry) rather than via ``add_extra_js_url`` (which runs before the swap and
gets dropped, yielding "custom element doesn't exist" on a hard refresh).
"""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant, callback

from custom_components.fado.card_resources import (
    async_register_card_resource,
    async_unregister_card_resource,
)

BASE_URL = "/fado_panel/fado-card.js"
CARD_URL = "/fado_panel/fado-card.js"
STORAGE_KEY = "card_resource_id"


class FakeResources:
    """Minimal stand-in for HA's Lovelace resource collection."""

    def __init__(self) -> None:
        self.loaded = False
        self._items: list[dict] = []
        self._next_id = 1
        self.create_calls: list[dict] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.delete_calls: list[str] = []

    async def async_load(self) -> None:
        self.loaded = True

    @callback
    def async_items(self) -> list[dict]:
        return list(self._items)

    async def async_create_item(self, data: dict) -> dict:
        item = {"id": str(self._next_id), **data}
        self._next_id += 1
        self._items.append(item)
        self.create_calls.append(data)
        return item

    async def async_update_item(self, item_id: str, data: dict) -> None:
        self.update_calls.append((item_id, data))
        for item in self._items:
            if item["id"] == item_id:
                item.update(data)

    async def async_delete_item(self, item_id: str) -> None:
        self.delete_calls.append(item_id)
        self._items = [item for item in self._items if item["id"] != item_id]


class FakeLovelace:
    """Stand-in for hass.data['lovelace']."""

    def __init__(self, resources: FakeResources) -> None:
        self.resources = resources


async def test_registers_card_as_lovelace_resource(hass: HomeAssistant) -> None:
    """A card with a Lovelace resource collection is registered as a module resource."""
    resources = FakeResources()
    hass.data["lovelace"] = FakeLovelace(resources)

    with patch("custom_components.fado.card_resources.frontend.add_extra_js_url") as mock_extra:
        await async_register_card_resource(hass, BASE_URL, CARD_URL, STORAGE_KEY)

    # Registered as a Lovelace resource, NOT via the (broken) extra-js path.
    assert resources.create_calls == [{"res_type": "module", "url": CARD_URL}]
    mock_extra.assert_not_called()


async def test_falls_back_to_extra_js_when_no_lovelace(hass: HomeAssistant) -> None:
    """Without a Lovelace resource collection (YAML mode), fall back to add_extra_js_url."""
    hass.data.pop("lovelace", None)

    with patch("custom_components.fado.card_resources.frontend.add_extra_js_url") as mock_extra:
        await async_register_card_resource(hass, BASE_URL, CARD_URL, STORAGE_KEY)

    mock_extra.assert_called_once_with(hass, CARD_URL)


async def test_idempotent_skips_existing_resource(hass: HomeAssistant) -> None:
    """An already-registered resource with the same url is not duplicated."""
    resources = FakeResources()
    resources._items.append({"id": "7", "res_type": "module", "url": CARD_URL})
    hass.data["lovelace"] = FakeLovelace(resources)

    await async_register_card_resource(hass, BASE_URL, CARD_URL, STORAGE_KEY)

    assert resources.create_calls == []
    assert resources.update_calls == []


async def test_updates_existing_resource_for_same_base_url(hass: HomeAssistant) -> None:
    """A stale resource for the same base_url is updated to the new card_url."""
    resources = FakeResources()
    resources._items.append({"id": "9", "res_type": "module", "url": f"{BASE_URL}?v=old"})
    hass.data["lovelace"] = FakeLovelace(resources)

    new_url = f"{BASE_URL}?v=new"
    await async_register_card_resource(hass, BASE_URL, new_url, STORAGE_KEY)

    assert resources.update_calls == [("9", {"url": new_url})]
    assert resources.create_calls == []


async def test_unregister_removes_resource(hass: HomeAssistant) -> None:
    """Unregister deletes the resource that registration created."""
    resources = FakeResources()
    hass.data["lovelace"] = FakeLovelace(resources)

    await async_register_card_resource(hass, BASE_URL, CARD_URL, STORAGE_KEY)
    created_id = resources._items[0]["id"]

    await async_unregister_card_resource(hass, CARD_URL, STORAGE_KEY)

    assert resources.delete_calls == [created_id]


async def test_unregister_falls_back_to_remove_extra_js(hass: HomeAssistant) -> None:
    """If registration used the extra-js fallback, unregister removes the extra-js url."""
    hass.data.pop("lovelace", None)

    with patch("custom_components.fado.card_resources.frontend.add_extra_js_url"):
        await async_register_card_resource(hass, BASE_URL, CARD_URL, STORAGE_KEY)

    with patch("custom_components.fado.card_resources.frontend.remove_extra_js_url") as mock_remove:
        await async_unregister_card_resource(hass, CARD_URL, STORAGE_KEY)

    mock_remove.assert_called_once_with(hass, CARD_URL)
