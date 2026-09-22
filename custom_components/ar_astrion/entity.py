"""Shared device identity for every AR Astrion entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AstrionCoordinator


class AstrionEntity(CoordinatorEntity[AstrionCoordinator]):
    """Base class tying an entity to the one remote its entry configures."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Attach to the coordinator and the device it represents."""
        super().__init__(coordinator)
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            manufacturer="Sanytron",
            model="Astrion HA100",
            name=coordinator.entry.title,
            sw_version=data.version if data else None,
            configuration_url=coordinator.api.base_url,
        )
