"""Receiving side: the remote POSTs here whenever something changes.

A webhook rather than a poll because the device is a battery-powered handheld
that spends most of its day asleep — and because a button press has to arrive
in milliseconds to be worth automating on at all.
"""

from __future__ import annotations

import logging

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response

from homeassistant.components import webhook
from homeassistant.core import HomeAssistant

from .const import CONF_WEBHOOK_ID, DOMAIN
from .coordinator import AstrionCoordinator

_LOGGER = logging.getLogger(__name__)

# The remote's pushes are tiny JSON objects; anything larger isn't ours.
MAX_PAYLOAD_BYTES = 8192


def async_register_webhook(
    hass: HomeAssistant, entry, coordinator: AstrionCoordinator
) -> None:
    """Register this entry's webhook and unregister it on unload."""
    webhook_id: str = entry.data[CONF_WEBHOOK_ID]

    async def handle(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response:
        """Hand one push to the coordinator."""
        if request.content_length and request.content_length > MAX_PAYLOAD_BYTES:
            return Response(status=413)
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.debug("Astrion webhook got a body that wasn't JSON")
            return Response(status=400)
        if not isinstance(payload, dict):
            return Response(status=400)
        coordinator.async_handle_push(payload)
        return Response(status=200)

    webhook.async_register(
        hass,
        DOMAIN,
        f"AR Astrion {entry.title}",
        webhook_id,
        handle,
        local_only=True,
        allowed_methods=[METH_POST],
    )
    entry.async_on_unload(lambda: webhook.async_unregister(hass, webhook_id))
    _LOGGER.debug("Registered Astrion webhook for %s", entry.title)
