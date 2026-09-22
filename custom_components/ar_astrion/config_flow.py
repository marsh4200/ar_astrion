"""Config flow: find the remote, then point its push back at us."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    ConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AstrionApi, AstrionApiError
from .const import (
    CONF_RELEASE_REPO,
    CONF_WEBHOOK_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RELEASE_REPO,
    DOMAIN,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class AstrionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one Astrion remote by address."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the remote's address and confirm something answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            api = AstrionApi(async_get_clientsession(self.hass), host, port)
            try:
                await api.version()
            except AstrionApiError:
                errors["base"] = "cannot_connect"
            else:
                # The device offers no serial or MAC over HTTP, so the address
                # is the only stable identity available — which also stops the
                # same remote being added twice.
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()

                webhook_id = webhook.async_generate_id()
                try:
                    await api.set_webhook_id(webhook_id)
                except AstrionApiError:
                    # Older builds have no /webhook-id endpoint. Everything
                    # still works by polling; only instant pushes (and with
                    # them the button events) need it, so say so rather than
                    # failing the whole setup.
                    errors["base"] = "no_webhook_endpoint"
                else:
                    return self.async_create_entry(
                        title=f"{DEFAULT_NAME} ({host})",
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_WEBHOOK_ID: webhook_id,
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> AstrionOptionsFlow:
        """Expose the release-repo option."""
        return AstrionOptionsFlow()


class AstrionOptionsFlow(OptionsFlow):
    """Which GitHub repo the update entity compares against."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let a fork point the update check at its own releases."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RELEASE_REPO,
                        default=self.config_entry.options.get(
                            CONF_RELEASE_REPO, DEFAULT_RELEASE_REPO
                        ),
                    ): str,
                }
            ),
        )
