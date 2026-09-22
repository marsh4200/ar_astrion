"""Battery level of the remote itself."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
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
    """Add the battery sensor."""
    async_add_entities([AstrionBatterySensor(entry.runtime_data.coordinator)])


class AstrionBatterySensor(AstrionEntity, SensorEntity):
    """Charge level, pushed on every change rather than polled.

    A handheld that sleeps most of the day is exactly the thing a polling
    loop keeps awake, so the app pushes this instead — see the integration's
    README on why the update interval is only a backstop.
    """

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Battery"

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Set the unique id from the config entry."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_battery"

    @property
    def native_value(self) -> int | None:
        """Charge percentage, or None while the device hasn't reported one."""
        return self.coordinator.data.battery_level if self.coordinator.data else None
