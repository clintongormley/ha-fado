"""Tests for Fado config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fado.const import (
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_SHOW_SIDEBAR,
    DOMAIN,
    OPTION_DASHBOARD_URL,
    OPTION_NOTIFICATIONS_ENABLED,
    OPTION_SHOW_SIDEBAR,
)


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test user flow creates config entry with title 'Fado'."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fado"
    assert result["data"] == {}


async def test_single_instance_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test second setup aborts with 'single_instance_allowed'."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test import flow creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fado"
    assert result["data"] == {}


async def test_import_flow_single_instance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test import flow aborts if instance exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_shows_form(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow shows form with defaults."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_saves_options(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow saves user input."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_SHOW_SIDEBAR: False,
            OPTION_NOTIFICATIONS_ENABLED: False,
            OPTION_DASHBOARD_URL: "/lovelace-fado/0",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][OPTION_SHOW_SIDEBAR] is False
    assert result["data"][OPTION_DASHBOARD_URL] == "/lovelace-fado/0"
    assert result["data"][OPTION_NOTIFICATIONS_ENABLED] is False


async def test_options_flow_defaults(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow uses correct defaults when no options set."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    # Submit with just defaults
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_SHOW_SIDEBAR: DEFAULT_SHOW_SIDEBAR,
            OPTION_NOTIFICATIONS_ENABLED: DEFAULT_NOTIFICATIONS_ENABLED,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][OPTION_SHOW_SIDEBAR] is True
