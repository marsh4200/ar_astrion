"""Charging state of the remote (it sits in a dock)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AstrionConfigEntry
from .coordinator import AstrionCoordinator
from .entity import AstrionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AstrionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the charging sensor."""
    async_add_entities([AstrionChargingSensor(entry.runtime_data.coordinator)])


class AstrionChargingSensor(AstrionEntity, BinarySensorEntity):
    """On while the remote is on its charge dock."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Charging"

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Set the unique id from the config entry."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_charging"

    @property
    def is_on(self) -> bool | None:
        """True when charging."""
        return self.coordinator.data.charging if self.coordinator.data else None
