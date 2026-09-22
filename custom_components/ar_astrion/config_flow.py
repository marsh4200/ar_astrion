"""Config flow: find the remote, then point its push back at us."""

from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)


def _normalise_host(raw: str, port: int) -> tuple[str, int]:
    """Accept whatever form of the address someone pastes in.

    The address people have in hand is the one the remote's Settings panel
    shows — `http://192.168.1.50:8080` — and pasting that whole thing used to
    produce `http://http://192.168.1.50:8080:8080` and a flat "cannot
    connect", with nothing to suggest the address itself was the problem.
    So: drop a scheme, drop a trailing slash, and take an inline `:port` over
    the port field.
    """
    host = raw.strip()
    for scheme in ("http://", "https://"):
        if host.lower().startswith(scheme):
            host = host[len(scheme) :]
    host = host.strip("/")
    if host.count(":") == 1:
        maybe_host, _, maybe_port = host.partition(":")
        if maybe_port.isdigit():
            host, port = maybe_host, int(maybe_port)
    return host, port


class AstrionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one Astrion remote by address."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the remote's address and confirm something answers there."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host, port = _normalise_host(user_input[CONF_HOST], user_input[CONF_PORT])
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
                except AstrionApiError as err:
                    # A build without POST /webhook-id can't be told where to
                    # push. That costs the button events and instant updates,
                    # but everything else works by polling — so this must NOT
                    # block setup. async_setup_entry retries the same call on
                    # every load, so the pushes start on their own once the
                    # remote is updated, with no need to re-add it here.
                    _LOGGER.warning(
                        "%s:%s accepted no webhook id (%s). Adding it anyway: "
                        "polling works, but button presses will not arrive "
                        "until the remote runs a build with POST /webhook-id",
                        host,
                        port,
                        err,
                    )
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
