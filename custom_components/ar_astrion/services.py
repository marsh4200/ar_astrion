"""Services that don't map onto an entity."""

from __future__ import annotations

import json

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .api import AstrionApi, AstrionApiError
from .const import (
    ATTR_CONFIG,
    ATTR_DURATION,
    ATTR_PATH,
    ATTR_SOUND,
    ATTR_VOLUME,
    DOMAIN,
    RING_SOUNDS,
    SERVICE_PUSH_DASHBOARD,
    SERVICE_RING,
)

ATTR_DEVICE_ID = "device_id"

PUSH_DASHBOARD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
        vol.Exclusive(ATTR_PATH, "source"): cv.string,
        vol.Exclusive(ATTR_CONFIG, "source"): dict,
    }
)

RING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
        vol.Optional(ATTR_SOUND, default="ringtone"): vol.In(RING_SOUNDS),
        vol.Optional(ATTR_VOLUME, default=80): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(ATTR_DURATION, default=15): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
    }
)


def _apis_for_call(hass: HomeAssistant, call: ServiceCall) -> list[AstrionApi]:
    """Resolve the targeted devices to their API clients."""
    registry = dr.async_get(hass)
    apis: list[AstrionApi] = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        device = registry.async_get(device_id)
        if device is None:
            raise ServiceValidationError(f"Unknown device: {device_id}")
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN:
                continue
            runtime = getattr(entry, "runtime_data", None)
            if runtime is not None:
                apis.append(runtime.api)
    if not apis:
        raise ServiceValidationError(
            "No loaded AR Astrion remote among the targeted devices"
        )
    return apis


async def _async_read_dashboard(hass: HomeAssistant, call: ServiceCall) -> bytes:
    """Get the dashboard JSON to upload, from a file or inline config."""
    if ATTR_CONFIG in call.data:
        return json.dumps(call.data[ATTR_CONFIG]).encode()

    path: str | None = call.data.get(ATTR_PATH)
    if not path:
        raise ServiceValidationError("Provide either 'path' or 'config'")
    if not hass.config.is_allowed_path(path):
        raise ServiceValidationError(
            f"{path} is not in allowlist_external_dirs, so Home Assistant "
            "may not read it"
        )

    def read() -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    try:
        content = await hass.async_add_executor_job(read)
    except OSError as err:
        raise ServiceValidationError(f"Could not read {path}: {err}") from err

    # Upload a broken file and the remote falls back to its built-in defaults
    # on next load, which looks like the dashboard vanishing. Cheaper to catch
    # it here.
    try:
        json.loads(content)
    except ValueError as err:
        raise ServiceValidationError(f"{path} is not valid JSON: {err}") from err
    return content


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_PUSH_DASHBOARD):
        return

    async def push_dashboard(call: ServiceCall) -> None:
        """Replace dashboard.json on the targeted remotes and reload them."""
        content = await _async_read_dashboard(hass, call)
        for api in _apis_for_call(hass, call):
            try:
                await api.push_dashboard(content)
            except AstrionApiError as err:
                raise HomeAssistantError(str(err)) from err

    async def ring(call: ServiceCall) -> None:
        """Make the targeted remotes ring so they can be found."""
        for api in _apis_for_call(hass, call):
            try:
                await api.ring(
                    sound=call.data[ATTR_SOUND],
                    volume=call.data[ATTR_VOLUME],
                    duration=call.data[ATTR_DURATION],
                )
            except AstrionApiError as err:
                raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN, SERVICE_PUSH_DASHBOARD, push_dashboard, schema=PUSH_DASHBOARD_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RING, ring, schema=RING_SCHEMA)
