"""Config flow for Fado integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback

from .const import (
    DEFAULT_DASHBOARD_URL,
    DEFAULT_NOTIFICATIONS_ENABLED,
    DEFAULT_SHOW_SIDEBAR,
    DOMAIN,
    OPTION_DASHBOARD_URL,
    OPTION_NOTIFICATIONS_ENABLED,
    OPTION_SHOW_SIDEBAR,
)


class FadoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fado."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        # Only allow a single instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Create entry immediately without showing a form
        return self.async_create_entry(
            title="Fado",
            data={},
        )

    async def async_step_import(
        self, _import_config: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle import from configuration.yaml or auto-setup."""
        # Only allow a single instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="Fado",
            data={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> FadoOptionsFlow:
        """Get the options flow for this handler."""
        return FadoOptionsFlow()


class FadoOptionsFlow(OptionsFlowWithReload):
    """Handle Fado options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        data_schema = vol.Schema(
            {
                vol.Required(
                    OPTION_SHOW_SIDEBAR,
                    default=options.get(OPTION_SHOW_SIDEBAR, DEFAULT_SHOW_SIDEBAR),
                ): bool,
                vol.Required(
                    OPTION_NOTIFICATIONS_ENABLED,
                    default=options.get(
                        OPTION_NOTIFICATIONS_ENABLED,
                        DEFAULT_NOTIFICATIONS_ENABLED,
                    ),
                ): bool,
                vol.Optional(
                    OPTION_DASHBOARD_URL,
                    description={
                        "suggested_value": options.get(OPTION_DASHBOARD_URL, DEFAULT_DASHBOARD_URL)
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
