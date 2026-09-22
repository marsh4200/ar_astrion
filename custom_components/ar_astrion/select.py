"""Selects: which page is on screen, and what's running in each room."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AstrionConfigEntry
from .const import DOMAIN
from .coordinator import AstrionCoordinator
from .entity import AstrionEntity

OPTION_OFF = "Off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AstrionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the page select, plus one Activity select per room found.

    Rooms come from the device's own Activity registry at setup time. A room
    added to dashboard.json later needs a reload of this entry to appear —
    creating entities on the fly from a push would leave stale ones behind
    every time a dashboard is edited.
    """
    coordinator = entry.runtime_data.coordinator
    entities: list[SelectEntity] = [AstrionPageSelect(coordinator)]
    entities.extend(
        AstrionActivitySelect(coordinator, room)
        for room in (coordinator.data.rooms() if coordinator.data else [])
    )
    async_add_entities(entities)


class AstrionPageSelect(AstrionEntity, SelectEntity):
    """The dashboard page currently on screen — readable and settable.

    Stays in sync with a swipe or a hardware button on the device itself,
    because the app pushes every page change, whatever caused it.
    """

    _attr_name = "Page"
    _attr_icon = "mdi:view-carousel"

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Set the unique id from the config entry."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_page"

    @property
    def options(self) -> list[str]:
        """Page names, in pager order."""
        return self.coordinator.data.pages if self.coordinator.data else []

    @property
    def current_option(self) -> str | None:
        """The page on screen, or None if it isn't in the list yet."""
        data = self.coordinator.data
        if not data or not data.page_name:
            return None
        return data.page_name if data.page_name in data.pages else None

    async def async_select_option(self, option: str) -> None:
        """Jump the device to that page."""
        await self.coordinator.api.set_page(option)
        # The device pushes the change itself; this just avoids a visible
        # lag in the UI if that push is dropped.
        await self.coordinator.async_request_refresh()


class AstrionActivitySelect(AstrionEntity, SelectEntity):
    """Which AV Activity is active in one room — start or stop it from here."""

    _attr_icon = "mdi:television-play"

    def __init__(self, coordinator: AstrionCoordinator, room: str) -> None:
        """Bind this entity to one room's Activities."""
        super().__init__(coordinator)
        self._room = room
        self._attr_name = f"{room} activity"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_activity_{room.lower().replace(' ', '_')}"
        )

    @property
    def options(self) -> list[str]:
        """Every Activity in this room, plus Off."""
        names = [
            a["name"]
            for a in self.coordinator.activity_in_room(self._room)
            if a.get("name")
        ]
        return [OPTION_OFF, *names]

    @property
    def current_option(self) -> str | None:
        """The running Activity's name, or Off."""
        data = self.coordinator.data
        if not data:
            return None
        active = data.active.get(self._room)
        if not active:
            return OPTION_OFF
        name = active.get("name")
        return name if name in self.options else OPTION_OFF

    async def async_select_option(self, option: str) -> None:
        """Start the chosen Activity, or stop whatever is running."""
        if option == OPTION_OFF:
            await self.coordinator.api.stop_activity(self._room)
            return
        for activity in self.coordinator.activity_in_room(self._room):
            if activity.get("name") == option:
                await self.coordinator.api.start_activity(activity["id"])
                return
        raise HomeAssistantError(
            f"{DOMAIN}: no Activity named {option!r} in room {self._room!r}"
        )
