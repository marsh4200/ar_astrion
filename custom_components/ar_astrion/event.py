"""One event entity per physical button on the remote.

This is the point of the integration: the app pushes every press, bound or
not, so all of the remote's buttons become automation triggers in Home
Assistant without any entry in the device's own dashboard.json.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AstrionConfigEntry
from .const import (
    ATTR_BOUND,
    ATTR_KEY,
    ATTR_KEY_CODE,
    ATTR_PAGE,
    HARDWARE_KEYS,
    KEY_UNKNOWN,
    PRESS_TYPES,
    SIGNAL_BUTTON,
)
from .coordinator import AstrionCoordinator
from .entity import AstrionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AstrionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one entity per known button, plus a catch-all for the rest."""
    coordinator = entry.runtime_data.coordinator
    entities = [
        AstrionButtonEvent(coordinator, key, label)
        for key, label in HARDWARE_KEYS.items()
    ]
    entities.append(
        AstrionButtonEvent(coordinator, KEY_UNKNOWN, "Unrecognised button")
    )
    async_add_entities(entities)


class AstrionButtonEvent(AstrionEntity, EventEntity):
    """Fires whenever the remote reports a press of its button."""

    _attr_event_types = PRESS_TYPES
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(
        self, coordinator: AstrionCoordinator, key: str, label: str
    ) -> None:
        """Bind this entity to one logical hardware key."""
        super().__init__(coordinator)
        self._key = key
        self.entity_description = EventEntityDescription(
            key=key.lower(),
            name=label,
        )
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key.lower()}"

    async def async_added_to_hass(self) -> None:
        """Listen for pushes for this key only."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_BUTTON.format(entry_id=self.coordinator.entry.entry_id),
                self._handle_press,
            )
        )

    @callback
    def _handle_press(self, press: dict[str, Any]) -> None:
        if press.get(ATTR_KEY) != self._key:
            return
        self._trigger_event(
            press["press"],
            {
                ATTR_KEY: self._key,
                ATTR_KEY_CODE: press.get(ATTR_KEY_CODE),
                # False when the press also went to the remote's own screen
                # (moving the focus highlight) or did nothing locally; True
                # when a dashboard.json binding ran as well, which is worth
                # checking before acting so one press isn't handled twice.
                ATTR_BOUND: press.get(ATTR_BOUND, False),
                ATTR_PAGE: press.get(ATTR_PAGE),
            },
        )
        self.async_write_ha_state()
