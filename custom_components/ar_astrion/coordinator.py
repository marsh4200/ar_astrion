"""State for one Astrion remote: pushed when it changes, polled as a backstop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AstrionApi, AstrionApiError
from .const import (
    ATTR_BOUND,
    ATTR_KEY,
    ATTR_KEY_CODE,
    ATTR_PAGE,
    CONF_RELEASE_REPO,
    DEFAULT_RELEASE_REPO,
    DOMAIN,
    PRESS_TYPES,
    SIGNAL_BUTTON,
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

GITHUB_LATEST = "https://api.github.com/repos/{repo}/releases/latest"


@dataclass(slots=True)
class AstrionData:
    """Everything the entities render, from either channel."""

    version: str | None = None
    version_code: int | None = None
    battery_level: int | None = None
    charging: bool = False
    page_index: int | None = None
    page_name: str | None = None
    pages: list[str] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)
    active: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    latest_version: str | None = None

    def rooms(self) -> list[str]:
        """Rooms that have at least one trackable Activity."""
        seen: list[str] = []
        for activity in self.activities:
            room = activity.get("room")
            if room and room not in seen:
                seen.append(room)
        for room in self.active:
            if room not in seen:
                seen.append(room)
        return seen


class AstrionCoordinator(DataUpdateCoordinator[AstrionData]):
    """Polls the remote occasionally; mostly just receives its pushes."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: AstrionApi
    ) -> None:
        """Set up the coordinator for one configured remote."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {api.host}",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.api = api
        self.entry = entry
        self._release_repo: str = entry.options.get(
            CONF_RELEASE_REPO, DEFAULT_RELEASE_REPO
        )

    async def _async_update_data(self) -> AstrionData:
        """Read the device, keeping whatever a failed sub-call can't refresh.

        Only /version is allowed to fail the refresh: it is the reachability
        probe. The rest degrade individually — /activities, for one, answers
        500 while the dashboard hasn't composed yet, which happens on every
        app restart and is not a reason to mark the device unavailable.
        """
        previous = self.data or AstrionData()

        try:
            version = await self.api.version()
        except AstrionApiError as err:
            raise UpdateFailed(str(err)) from err

        battery, page, pages, activities, active = await asyncio.gather(
            self.api.battery(),
            self.api.current_page(),
            self.api.pages(),
            self.api.activities(),
            self.api.active_activities(),
            return_exceptions=True,
        )

        def ok(value: Any, fallback: Any) -> Any:
            if isinstance(value, BaseException):
                _LOGGER.debug("Astrion partial read failed: %s", value)
                return fallback
            return value

        battery = ok(battery, {})
        page = ok(page, {})
        pages = ok(pages, previous.pages)
        activities = ok(activities, previous.activities)
        active = ok(active, previous.active)

        level = battery.get("level")
        return AstrionData(
            version=version.get("version"),
            version_code=version.get("versionCode"),
            battery_level=int(level) if isinstance(level, (int, float)) else None,
            charging=bool(battery.get("charging", previous.charging)),
            page_index=page.get("index", previous.page_index),
            page_name=page.get("name", previous.page_name),
            pages=list(pages),
            activities=list(activities),
            active=dict(active),
            latest_version=await self._async_latest_version(previous.latest_version),
        )

    async def _async_latest_version(self, fallback: str | None) -> str | None:
        """Newest published APK version, from GitHub Releases.

        The device has no endpoint that reports this as data — its own
        /check-update answers with an HTML redirect for the browser — so the
        comparison the update entity needs is resolved here instead. A failure
        (rate limit, no network, renamed repo) keeps the previous answer and
        never fails the refresh.
        """
        if not self._release_repo:
            return fallback
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                GITHUB_LATEST.format(repo=self._release_repo),
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/vnd.github+json"},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("GitHub releases returned HTTP %s", resp.status)
                    return fallback
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Could not read latest release: %s", err)
            return fallback
        if not isinstance(payload, dict):
            return fallback
        tag = payload.get("tag_name") or payload.get("name")
        if not isinstance(tag, str):
            return fallback
        return tag.lstrip("vV") or fallback

    @callback
    def async_handle_push(self, payload: dict[str, Any]) -> None:
        """Apply one webhook push from the remote.

        Button presses are events, not state, so they go straight out on the
        dispatcher; everything else is merged into the current snapshot so a
        push never blanks a field it doesn't carry.
        """
        kind = payload.get("type")
        if kind == "button":
            self._async_dispatch_button(payload)
            return

        current = self.data or AstrionData()
        if kind == "page":
            index = payload.get("index")
            updated = replace(
                current,
                page_index=index if isinstance(index, int) else current.page_index,
                page_name=payload.get("name") or current.page_name,
            )
        elif kind == "battery":
            level = payload.get("level")
            updated = replace(
                current,
                battery_level=int(level)
                if isinstance(level, (int, float))
                else current.battery_level,
                charging=bool(payload.get("charging", current.charging)),
            )
        elif kind == "activity":
            rooms = payload.get("rooms")
            if not isinstance(rooms, dict):
                return
            merged = dict(current.active)
            merged.update(rooms)
            updated = replace(current, active=merged)
        else:
            _LOGGER.debug("Ignoring unknown Astrion push type: %s", kind)
            return

        self.async_set_updated_data(updated)

    @callback
    def _async_dispatch_button(self, payload: dict[str, Any]) -> None:
        press = payload.get("press")
        key = payload.get(ATTR_KEY)
        if press not in PRESS_TYPES or not isinstance(key, str):
            _LOGGER.debug("Discarding malformed button push: %s", payload)
            return
        async_dispatcher_send(
            self.hass,
            SIGNAL_BUTTON.format(entry_id=self.entry.entry_id),
            {
                ATTR_KEY: key,
                "press": press,
                ATTR_KEY_CODE: payload.get("keyCode"),
                ATTR_BOUND: bool(payload.get("bound", False)),
                ATTR_PAGE: payload.get("page"),
            },
        )

    def activity_in_room(self, room: str) -> list[dict[str, Any]]:
        """Trackable Activities belonging to one room."""
        data = self.data or AstrionData()
        return [a for a in data.activities if a.get("room") == room]
