"""Tests for unconfigured lights notification."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.light.const import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fado import async_setup_entry
from custom_components.fado.const import (
    DOMAIN,
    NOTIFICATION_ID,
    OPTION_DASHBOARD_URL,
    OPTION_NOTIFICATIONS_ENABLED,
    OPTION_SHOW_SIDEBAR,
)
from custom_components.fado.coordinator import FadeCoordinator
from custom_components.fado.notifications import (
    _get_notification_link_url,
    _get_unconfigured_lights,
    _notify_unconfigured_lights,
)


def _make_coordinator(hass: HomeAssistant, data: dict | None = None) -> FadeCoordinator:
    """Create a FadeCoordinator with mock store and given data."""
    mock_store = MagicMock()
    mock_store.async_save = AsyncMock()
    coordinator = FadeCoordinator(
        hass=hass,
        store=mock_store,
        min_step_delay_ms=100,
    )
    if data is not None:
        coordinator.data = data
    hass.data[DOMAIN] = coordinator
    return coordinator


@pytest.fixture
def mock_entity_registry():
    """Create a mock entity registry."""
    registry = MagicMock()
    return registry


class TestGetUnconfiguredLights:
    """Test _get_unconfigured_lights function."""

    def test_returns_empty_when_domain_not_loaded(self, hass: HomeAssistant) -> None:
        """Test returns empty set when domain not in hass.data."""
        with patch("custom_components.fado.notifications.er.async_get") as mock_er:
            mock_er.return_value.entities = {}
            result = _get_unconfigured_lights(hass)
        assert result == set()

    def test_returns_unconfigured_light(self, hass: HomeAssistant) -> None:
        """Test returns light missing min_delay_ms."""
        _make_coordinator(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with patch("custom_components.fado.notifications.er.async_get") as mock_er:
            mock_er.return_value.entities.values.return_value = [mock_entry]
            result = _get_unconfigured_lights(hass)

        assert result == {"light.bedroom"}

    def test_excludes_configured_light(self, hass: HomeAssistant) -> None:
        """Test excludes light with all required fields configured."""
        _make_coordinator(
            hass,
            {
                "light.bedroom": {
                    "min_delay_ms": 100,
                    "min_brightness": 1,
                    "native_transitions": True,
                }
            },
        )

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with patch("custom_components.fado.notifications.er.async_get") as mock_er:
            mock_er.return_value.entities.values.return_value = [mock_entry]
            result = _get_unconfigured_lights(hass)

        assert result == set()

    def test_excludes_disabled_light(self, hass: HomeAssistant) -> None:
        """Test excludes disabled lights."""
        _make_coordinator(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = True

        with patch("custom_components.fado.notifications.er.async_get") as mock_er:
            mock_er.return_value.entities.values.return_value = [mock_entry]
            result = _get_unconfigured_lights(hass)

        assert result == set()

    def test_excludes_excluded_light(self, hass: HomeAssistant) -> None:
        """Test excludes lights marked as excluded."""
        _make_coordinator(hass, {"light.bedroom": {"exclude": True}})

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with patch("custom_components.fado.notifications.er.async_get") as mock_er:
            mock_er.return_value.entities.values.return_value = [mock_entry]
            result = _get_unconfigured_lights(hass)

        assert result == set()

    def test_excludes_non_light_entities(self, hass: HomeAssistant) -> None:
        """Test excludes non-light domain entities."""
        _make_coordinator(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "switch.bedroom"
        mock_entry.domain = "switch"
        mock_entry.disabled = False

        with patch("custom_components.fado.notifications.er.async_get") as mock_er:
            mock_er.return_value.entities.values.return_value = [mock_entry]
            result = _get_unconfigured_lights(hass)

        assert result == set()


class TestNotifyUnconfiguredLights:
    """Test _notify_unconfigured_lights function."""

    async def test_creates_notification_when_unconfigured(self, hass: HomeAssistant) -> None:
        """Test creates notification when lights are unconfigured."""
        _make_coordinator(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_create"
            ) as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert "1 light" in call_args[0][1]
        assert "/fado" in call_args[0][1]

    async def test_creates_notification_plural(self, hass: HomeAssistant) -> None:
        """Test notification message is plural for multiple lights."""
        _make_coordinator(hass)

        mock_entries = []
        for name in ["bedroom", "kitchen"]:
            entry = MagicMock()
            entry.entity_id = f"light.{name}"
            entry.domain = LIGHT_DOMAIN
            entry.disabled = False
            mock_entries.append(entry)

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_create"
            ) as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = mock_entries
            await _notify_unconfigured_lights(hass)

        call_args = mock_create.call_args
        assert "2 lights" in call_args[0][1]

    async def test_dismisses_notification_when_all_configured(self, hass: HomeAssistant) -> None:
        """Test dismisses notification when no unconfigured lights."""
        _make_coordinator(
            hass,
            {
                "light.bedroom": {
                    "min_delay_ms": 100,
                    "min_brightness": 1,
                    "native_transitions": True,
                }
            },
        )

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_dismiss"
            ) as mock_dismiss,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_dismiss.assert_called_once_with(hass, NOTIFICATION_ID)

    async def test_dismisses_notification_when_no_lights(self, hass: HomeAssistant) -> None:
        """Test dismisses notification when no lights exist."""
        _make_coordinator(hass)

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_dismiss"
            ) as mock_dismiss,
        ):
            mock_er.return_value.entities.values.return_value = []
            await _notify_unconfigured_lights(hass)

        mock_dismiss.assert_called_once_with(hass, NOTIFICATION_ID)


class TestNotifySkippedBeforeStart:
    """Test that notifications are skipped before HA has fully started."""

    async def test_skips_when_ha_not_running(self, hass: HomeAssistant) -> None:
        """Test notification is skipped when hass.state is not running."""
        _make_coordinator(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        hass.state = CoreState.starting

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_create"
            ) as mock_create,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_dismiss"
            ) as mock_dismiss,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        # Neither create nor dismiss should be called before HA is running
        mock_create.assert_not_called()
        mock_dismiss.assert_not_called()

    async def test_entity_registry_create_during_startup_no_notification(
        self, hass: HomeAssistant
    ) -> None:
        """Test that entity registry create events during startup don't trigger notifications."""
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

        # HA is still starting at this point
        hass.state = CoreState.starting

        with patch(
            "custom_components.fado.notifications.persistent_notification.async_create"
        ) as mock_create:
            # Simulate entity registry create event (happens during startup)
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {"action": "create", "entity_id": "light.new_group"},
            )
            await hass.async_block_till_done()

        # Should not create notification while HA is still starting
        mock_create.assert_not_called()


class TestSetupNotification:
    """Test notification on setup."""

    async def test_checks_unconfigured_after_start(self, hass: HomeAssistant) -> None:
        """Test that unconfigured check waits for homeassistant_started during initial boot."""
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        # Simulate HA still starting (initial boot, not a reload)
        hass.state = CoreState.starting

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]  # Skip panel registration
            await async_setup_entry(hass, mock_entry)

            # Not called during setup (states may not be loaded yet)
            mock_notify.assert_not_called()

            # Fire the started event (all entity states now available)
            hass.bus.async_fire("homeassistant_started")
            await hass.async_block_till_done()

        mock_notify.assert_called_once_with(hass)

    async def test_checks_unconfigured_immediately_when_running(self, hass: HomeAssistant) -> None:
        """Test that unconfigured check runs immediately during a reload."""
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        # hass.is_running is True by default (simulating a reload)

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None
            await async_setup_entry(hass, mock_entry)

        # Called immediately during setup since HA is already running
        mock_notify.assert_called_once_with(hass)


class TestEntityRegistryNotification:
    """Test notification on entity registry events."""

    async def test_notifies_on_light_create(self, hass: HomeAssistant) -> None:
        """Test notification check on light entity creation."""
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

            # Reset mock to clear the call from setup
            mock_notify.reset_mock()

            # Simulate entity registry create event
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {"action": "create", "entity_id": "light.new_light"},
            )
            await hass.async_block_till_done()

            mock_notify.assert_called()

    async def test_notifies_on_light_reenable(self, hass: HomeAssistant) -> None:
        """Test notification check when light is re-enabled."""
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

            # Reset mock to clear the call from setup
            mock_notify.reset_mock()

            # Simulate entity registry update with disabled_by change
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {
                    "action": "update",
                    "entity_id": "light.bedroom",
                    "changes": {"disabled_by": None},
                },
            )
            await hass.async_block_till_done()

            mock_notify.assert_called()

    async def test_notifies_on_light_remove(self, hass: HomeAssistant) -> None:
        """Test notification check on light removal (may dismiss)."""
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

            # Reset mock to clear the call from setup
            mock_notify.reset_mock()

            # Simulate entity registry remove event
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {"action": "remove", "entity_id": "light.old_light"},
            )
            await hass.async_block_till_done()

            mock_notify.assert_called()

    async def test_ignores_non_light_entities(self, hass: HomeAssistant) -> None:
        """Test ignores non-light entity events."""
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

            # Reset mock to clear the call from setup
            mock_notify.reset_mock()

            # Simulate switch entity creation
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {"action": "create", "entity_id": "switch.new_switch"},
            )
            await hass.async_block_till_done()

            mock_notify.assert_not_called()

    async def test_ignores_update_without_disabled_change(self, hass: HomeAssistant) -> None:
        """Test ignores updates that don't change disabled state."""
        from homeassistant.helpers import entity_registry as er

        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        mock_entry.async_on_unload = MagicMock()

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights") as mock_notify,
            patch("custom_components.fado._apply_stored_log_level"),
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

            # Reset mock to clear the call from setup
            mock_notify.reset_mock()

            # Simulate entity registry update without disabled_by change
            hass.bus.async_fire(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                {
                    "action": "update",
                    "entity_id": "light.bedroom",
                    "changes": {"name": "New Name"},
                },
            )
            await hass.async_block_till_done()

            mock_notify.assert_not_called()


class TestDailyNotificationTimer:
    """Test daily notification timer."""

    async def test_registers_daily_timer(self, hass: HomeAssistant) -> None:
        """Test that setup registers a daily timer."""
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        unload_callbacks = []
        mock_entry.async_on_unload = lambda cb: unload_callbacks.append(cb)

        with (
            patch("custom_components.fado.async_register_websocket_api"),
            patch("custom_components.fado._notify_unconfigured_lights"),
            patch("custom_components.fado._apply_stored_log_level"),
            patch("custom_components.fado.async_track_time_interval") as mock_timer,
        ):
            hass.http = None  # type: ignore[assignment]
            await async_setup_entry(hass, mock_entry)

        # Verify timer was registered with 24 hour interval
        mock_timer.assert_called_once()
        call_args = mock_timer.call_args
        assert call_args[0][0] is hass  # First arg is hass
        assert call_args[0][2] == timedelta(hours=24)  # Third arg is interval


class TestPruneStaleStorage:
    """Test async_prune_stale_storage removes non-light entities."""

    async def test_prunes_non_light_entities(self, hass: HomeAssistant) -> None:
        """Test that non-light entities are removed from storage."""
        coordinator = _make_coordinator(
            hass,
            {
                "light.bedroom": {"min_delay_ms": 100},
                "event.kitchen_input_1": {"exclude": True},
                "sensor.temperature": {"orig_brightness": 200},
            },
        )

        mock_registry = MagicMock()
        mock_entry = MagicMock(entity_id="light.bedroom", domain=LIGHT_DOMAIN)
        mock_registry.async_get = lambda eid: mock_entry if eid == "light.bedroom" else None

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            await coordinator.async_prune_stale_storage()

        assert "light.bedroom" in coordinator.data
        assert "event.kitchen_input_1" not in coordinator.data
        assert "sensor.temperature" not in coordinator.data
        coordinator.store.async_save.assert_called_once()  # type: ignore[union-attr]

    async def test_keeps_valid_light_entities(self, hass: HomeAssistant) -> None:
        """Test that valid light entities are kept in storage."""
        coordinator = _make_coordinator(
            hass,
            {
                "light.bedroom": {"min_delay_ms": 100},
                "light.kitchen": {"min_delay_ms": 150},
            },
        )

        mock_registry = MagicMock()
        mock_entries = {
            "light.bedroom": MagicMock(entity_id="light.bedroom"),
            "light.kitchen": MagicMock(entity_id="light.kitchen"),
        }
        mock_registry.async_get = lambda eid: mock_entries.get(eid)

        with patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=mock_registry,
        ):
            await coordinator.async_prune_stale_storage()

        assert "light.bedroom" in coordinator.data
        assert "light.kitchen" in coordinator.data
        coordinator.store.async_save.assert_not_called()  # type: ignore[union-attr]


class TestSaveConfigNotification:
    """Test notification after saving config."""

    async def test_notifies_after_save(self, hass: HomeAssistant) -> None:
        """Test notification check is called after saving config."""
        from custom_components.fado.websocket_api import async_save_light_config

        _make_coordinator(hass)

        with patch(
            "custom_components.fado.websocket_api._notify_unconfigured_lights"
        ) as mock_notify:
            await async_save_light_config(hass, "light.bedroom", min_delay_ms=100)

        mock_notify.assert_called_once_with(hass)


class TestNotificationLinkUrl:
    """Test _get_notification_link_url returns correct URL based on options."""

    def test_sidebar_enabled_returns_fado(self, hass: HomeAssistant) -> None:
        """Test sidebar enabled returns /fado."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={OPTION_SHOW_SIDEBAR: True},
        )
        entry.add_to_hass(hass)

        assert _get_notification_link_url(hass) == "/fado"

    def test_sidebar_disabled_returns_dashboard_url(self, hass: HomeAssistant) -> None:
        """Test sidebar disabled returns configured dashboard URL."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                OPTION_SHOW_SIDEBAR: False,
                OPTION_DASHBOARD_URL: "/lovelace-fado/0",
            },
        )
        entry.add_to_hass(hass)

        assert _get_notification_link_url(hass) == "/lovelace-fado/0"

    def test_sidebar_disabled_blank_url_returns_empty(self, hass: HomeAssistant) -> None:
        """Test sidebar disabled with blank URL returns empty string."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                OPTION_SHOW_SIDEBAR: False,
                OPTION_DASHBOARD_URL: "",
            },
        )
        entry.add_to_hass(hass)

        assert _get_notification_link_url(hass) == ""

    def test_sidebar_disabled_no_url_returns_empty(self, hass: HomeAssistant) -> None:
        """Test sidebar disabled with no dashboard URL returns empty string."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            options={OPTION_SHOW_SIDEBAR: False},
        )
        entry.add_to_hass(hass)

        assert _get_notification_link_url(hass) == ""

    def test_no_config_entry_returns_fado(self, hass: HomeAssistant) -> None:
        """Test returns /fado when no config entry exists."""
        assert _get_notification_link_url(hass) == "/fado"


class TestNotificationsDisabled:
    """Test notifications can be disabled via options."""

    async def test_disabled_notifications_dismisses(self, hass: HomeAssistant) -> None:
        """Test disabled notifications dismisses any existing notification."""
        _make_coordinator(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            options={OPTION_NOTIFICATIONS_ENABLED: False},
        )
        entry.add_to_hass(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_create"
            ) as mock_create,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_dismiss"
            ) as mock_dismiss,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        # Should dismiss, not create
        mock_create.assert_not_called()
        mock_dismiss.assert_called_once_with(hass, NOTIFICATION_ID)

    async def test_sidebar_disabled_uses_dashboard_url(self, hass: HomeAssistant) -> None:
        """Test notification uses dashboard URL when sidebar is disabled."""
        _make_coordinator(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                OPTION_SHOW_SIDEBAR: False,
                OPTION_DASHBOARD_URL: "/lovelace-fado/0",
                OPTION_NOTIFICATIONS_ENABLED: True,
            },
        )
        entry.add_to_hass(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_create"
            ) as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert "/lovelace-fado/0" in call_args[0][1]
        assert "/fado" not in call_args[0][1]

    async def test_sidebar_disabled_no_url_no_link(self, hass: HomeAssistant) -> None:
        """Test notification has no link when sidebar disabled and no dashboard URL."""
        _make_coordinator(hass)

        entry = MockConfigEntry(
            domain=DOMAIN,
            options={
                OPTION_SHOW_SIDEBAR: False,
                OPTION_NOTIFICATIONS_ENABLED: True,
            },
        )
        entry.add_to_hass(hass)

        mock_entry = MagicMock()
        mock_entry.entity_id = "light.bedroom"
        mock_entry.domain = LIGHT_DOMAIN
        mock_entry.disabled = False

        with (
            patch("custom_components.fado.notifications.er.async_get") as mock_er,
            patch(
                "custom_components.fado.notifications.persistent_notification.async_create"
            ) as mock_create,
        ):
            mock_er.return_value.entities.values.return_value = [mock_entry]
            await _notify_unconfigured_lights(hass)

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        # Should have base message without any link
        assert "Configure now" not in call_args[0][1]
        assert "1 light" in call_args[0][1]
