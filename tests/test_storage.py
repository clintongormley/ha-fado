"""Tests for storage helpers."""

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.fade_lights import (
    _get_light_config,
    _get_orig_brightness,
    _store_orig_brightness,
)
from custom_components.fade_lights.const import DOMAIN


@pytest.fixture
def hass_with_storage(hass: HomeAssistant) -> HomeAssistant:
    """Set up hass with storage data."""
    hass.data[DOMAIN] = {
        "data": {
            "light.bedroom": {
                "orig_brightness": 200,
                "min_delay_ms": 150,
                "exclude": True,
            },
            "light.kitchen": {
                "orig_brightness": 255,
            },
        },
        "store": MagicMock(),
    }
    return hass


class TestGetLightConfig:
    """Test _get_light_config helper."""

    def test_returns_config_for_configured_light(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test that config is returned for a configured light."""
        config = _get_light_config(hass_with_storage, "light.bedroom")

        assert config["min_delay_ms"] == 150
        assert config["exclude"] is True

    def test_returns_empty_dict_for_unconfigured_light(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test that empty dict is returned for unconfigured light."""
        config = _get_light_config(hass_with_storage, "light.unknown")

        assert config == {}

    def test_returns_empty_dict_when_domain_not_loaded(
        self, hass: HomeAssistant
    ) -> None:
        """Test that empty dict is returned when domain not loaded."""
        config = _get_light_config(hass, "light.bedroom")

        assert config == {}


class TestGetOrigBrightness:
    """Test _get_orig_brightness with new storage structure."""

    def test_returns_brightness_from_nested_structure(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test brightness is read from nested dict."""
        brightness = _get_orig_brightness(hass_with_storage, "light.bedroom")

        assert brightness == 200

    def test_returns_zero_for_unconfigured_light(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test zero is returned for unconfigured light."""
        brightness = _get_orig_brightness(hass_with_storage, "light.unknown")

        assert brightness == 0


class TestStoreOrigBrightness:
    """Test _store_orig_brightness with new storage structure."""

    def test_stores_brightness_in_nested_structure(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test brightness is stored in nested dict."""
        _store_orig_brightness(hass_with_storage, "light.bedroom", 180)

        assert hass_with_storage.data[DOMAIN]["data"]["light.bedroom"]["orig_brightness"] == 180

    def test_creates_entry_for_new_light(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test new entry is created for unconfigured light."""
        _store_orig_brightness(hass_with_storage, "light.new", 100)

        assert hass_with_storage.data[DOMAIN]["data"]["light.new"]["orig_brightness"] == 100

    def test_preserves_other_config_when_updating(
        self, hass_with_storage: HomeAssistant
    ) -> None:
        """Test other config fields are preserved when updating brightness."""
        _store_orig_brightness(hass_with_storage, "light.bedroom", 180)

        config = hass_with_storage.data[DOMAIN]["data"]["light.bedroom"]
        assert config["orig_brightness"] == 180
        assert config["min_delay_ms"] == 150  # Preserved
        assert config["exclude"] is True  # Preserved
