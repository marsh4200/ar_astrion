"""AR Astrion Remote — Home Assistant integration for a Sanytron Astrion HA100
running Astrion Custom Dashboard.

The app on the remote is already an HA websocket client, so this integration
isn't what connects the two. It is the companion half: it turns the remote
into a device in Home Assistant — every physical button as an event entity,
the page on screen as a select, battery, AV Activities, app updates — by
talking to the small HTTP API the app serves on port 8080 and receiving the
pushes it sends to a webhook.

See docs/COMPANION_INTEGRATION.md in the app repo for the device contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AstrionApi, AstrionApiError
from .const import CONF_WEBHOOK_ID
from .coordinator import AstrionCoordinator
from .services import async_setup_services
from .webhook import async_register_webhook

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.UPDATE,
]


@dataclass(slots=True)
class AstrionRuntimeData:
    """What the platforms and services need, per configured remote."""

    api: AstrionApi
    coordinator: AstrionCoordinator


# Plain alias rather than a PEP 695 `type` statement: identical for typing,
# and it keeps the file importable on any Python a tool might parse it with.
AstrionConfigEntry = ConfigEntry[AstrionRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Set up one remote."""
    api = AstrionApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )
    coordinator = AstrionCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AstrionRuntimeData(api=api, coordinator=coordinator)

    async_register_webhook(hass, entry, coordinator)

    # Re-assert the webhook id on every setup. The remote stores it in its own
    # prefs, so anything that clears app data — a reinstall, a factory reset,
    # someone saving the connection form in the web configurator with the
    # field blank — silently stops the pushes. Cheap to send, and it's the
    # difference between the button entities working and never firing.
    try:
        await api.set_webhook_id(entry.data[CONF_WEBHOOK_ID])
    except AstrionApiError as err:
        _LOGGER.warning(
            "Could not set the webhook id on %s (%s). Polling still works, but "
            "button presses and instant updates will not arrive until it does",
            entry.title,
            err,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> bool:
    """Unload one remote."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: AstrionConfigEntry) -> None:
    """Reload after an options change (e.g. a different release repo)."""
    await hass.config_entries.async_reload(entry.entry_id)
