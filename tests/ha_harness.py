"""One import path for the HA test helpers, on old and new HA."""

try:
    from pytest_homeassistant.common import MockConfigEntry, MockUser
except ImportError:
    from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

__all__ = ["MockConfigEntry", "MockUser"]
