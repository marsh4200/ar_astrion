"""HTTP client for an Astrion remote's on-device ConfigServer (port 8080).

The remote is a Home Assistant *client* in its own right — it holds a
long-lived token and talks the websocket API directly — so this is not how
the dashboard reaches HA. It is the other direction: the small unauthenticated
HTTP API the app exposes on the LAN for a controller like this integration.

Documented in the app repo as docs/COMPANION_INTEGRATION.md. Two of its
endpoints answer with an HTML redirect rather than JSON (/check-update and
/install-update, both written for a browser); those are treated as
fire-and-forget here.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)
# A dashboard upload writes to /sdcard and live-reloads the UI.
UPLOAD_TIMEOUT = aiohttp.ClientTimeout(total=30)


class AstrionApiError(Exception):
    """The remote could not be reached, or answered with an error."""


class AstrionApi:
    """Thin wrapper over the remote's ConfigServer endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
    ) -> None:
        """Store the connection details; nothing is contacted until a call."""
        self._session = session
        self.host = host
        self.port = port

    @property
    def base_url(self) -> str:
        """Root of the device's configuration server."""
        return f"http://{self.host}:{self.port}"

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def _get_json(self, path: str) -> Any:
        try:
            async with self._session.get(self._url(path), timeout=TIMEOUT) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise AstrionApiError(f"GET {path} failed: {err}") from err

    async def _post_form(self, path: str, data: dict[str, str]) -> None:
        """POST a urlencoded form, ignoring the body.

        Several of these endpoints answer with an HTML redirect intended for
        the web configurator, so only the status code is meaningful.
        """
        try:
            async with self._session.post(
                self._url(path), data=data, timeout=TIMEOUT
            ) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AstrionApiError(f"POST {path} failed: {err}") from err

    # ---- reads ---------------------------------------------------------

    async def version(self) -> dict[str, Any]:
        """`{"version": "1.1.6", "versionCode": N}` — also the reachability probe."""
        data = await self._get_json("/version")
        if not isinstance(data, dict) or "version" not in data:
            raise AstrionApiError("/version did not look like an Astrion remote")
        return data

    async def battery(self) -> dict[str, Any]:
        """`{"level": 0-100 | None, "charging": bool}`."""
        data = await self._get_json("/battery")
        return data if isinstance(data, dict) else {}

    async def current_page(self) -> dict[str, Any]:
        """`{"index": N, "name": "..."}` for the page on screen right now."""
        data = await self._get_json("/current-page")
        return data if isinstance(data, dict) else {}

    async def pages(self) -> list[str]:
        """Page names in pager order."""
        data = await self._get_json("/pages")
        if not isinstance(data, list):
            return []
        return [p["name"] for p in data if isinstance(p, dict) and p.get("name")]

    async def activities(self) -> list[dict[str, Any]]:
        """Every trackable AV Activity: `[{id, name, room, icon}]`.

        Answers 500 when the dashboard hasn't composed yet, which is normal
        during a restart — the caller treats that as "none known".
        """
        data = await self._get_json("/activities")
        return [a for a in data if isinstance(a, dict)] if isinstance(data, list) else []

    async def active_activities(self) -> dict[str, Any]:
        """`{"<room>": {id, name} | null}` — what's running where."""
        data = await self._get_json("/activities/active")
        return data if isinstance(data, dict) else {}

    # ---- writes --------------------------------------------------------

    async def set_webhook_id(self, webhook_id: str) -> None:
        """Point the device's push at this integration's webhook.

        Uses the dedicated endpoint, never /save-connection: that one is the
        web configurator's whole-form handler and rebuilds the Harmony hub and
        IR extender lists from the request body, so a single-field POST to it
        would wipe both.
        """
        await self._post_form("/webhook-id", {"webhook_id": webhook_id})

    async def set_page(self, name: str) -> None:
        """Jump the dashboard to a page by name (case-insensitive)."""
        await self._post_form("/set-page", {"page": name})

    async def start_activity(self, activity_id: str) -> None:
        """Run an Activity's start sequence; room-exclusive on the device."""
        await self._post_form("/activities/start", {"id": activity_id})

    async def stop_activity(self, room: str) -> None:
        """Stop whatever Activity is active in a room."""
        await self._post_form("/activities/stop", {"room": room})

    async def ring(
        self,
        sound: str = "ringtone",
        volume: int = 80,
        duration: int = 15,
    ) -> None:
        """Play a locate sound on the remote (it clamps volume 1-100, duration 1-60)."""
        await self._post_form(
            "/ring",
            {"sound": sound, "volume": str(volume), "duration": str(duration)},
        )

    async def stop_ring(self) -> None:
        """Silence a ring in progress."""
        await self._post_form("/ring/stop", {})

    async def install_update(self) -> None:
        """Ask the device to download the newer APK and open Android's installer.

        The device answers with an HTML page either way, so a 200 means "the
        request landed", not "the update installed" — Android still needs
        "install unknown apps" granted for Astrion, and someone has to tap
        through the installer on the remote itself.
        """
        await self._post_form("/install-update", {})

    async def push_dashboard(self, content: bytes) -> None:
        """Replace dashboard.json and live-reload the dashboard.

        Multipart with the field named `file` — that is what NanoHTTPD writes
        to a temp file for the handler to copy into place.
        """
        form = aiohttp.FormData()
        form.add_field(
            "file", content, filename="dashboard.json", content_type="application/json"
        )
        try:
            async with self._session.post(
                self._url("/dashboard.json"), data=form, timeout=UPLOAD_TIMEOUT
            ) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AstrionApiError(f"dashboard upload failed: {err}") from err
