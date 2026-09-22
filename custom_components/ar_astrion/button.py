"""Buttons: find the remote, and stop it ringing."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AstrionConfigEntry
from .api import AstrionApi
from .coordinator import AstrionCoordinator
from .entity import AstrionEntity


@dataclass(frozen=True, kw_only=True)
class AstrionButtonDescription(ButtonEntityDescription):
    """A button and the call it makes."""

    press_fn: Callable[[AstrionApi], Coroutine[Any, Any, None]]


BUTTONS: tuple[AstrionButtonDescription, ...] = (
    AstrionButtonDescription(
        key="ring",
        name="Ring",
        icon="mdi:bell-ring",
        press_fn=lambda api: api.ring(),
    ),
    AstrionButtonDescription(
        key="stop_ring",
        name="Stop ringing",
        icon="mdi:bell-off",
        press_fn=lambda api: api.stop_ring(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AstrionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the locate buttons."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(AstrionButton(coordinator, desc) for desc in BUTTONS)


class AstrionButton(AstrionEntity, ButtonEntity):
    """Fires one ConfigServer call on press."""

    entity_description: AstrionButtonDescription

    def __init__(
        self, coordinator: AstrionCoordinator, description: AstrionButtonDescription
    ) -> None:
        """Wire the description's call to this entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    async def async_press(self) -> None:
        """Make the call."""
        await self.entity_description.press_fn(self.coordinator.api)
