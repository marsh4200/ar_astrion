"""APK update entity for the remote."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
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
    """Add the update entity."""
    async_add_entities([AstrionUpdate(entry.runtime_data.coordinator)])


class AstrionUpdate(AstrionEntity, UpdateEntity):
    """Installed app version against the newest published release.

    Installing is only a request: the device downloads the APK and opens
    Android's own installer, which needs "install unknown apps" granted for
    Astrion and someone to tap through it on the remote. So this reports
    success as soon as the request lands, not when the new build is running —
    the installed version won't move until the app restarts.
    """

    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_name = "Firmware"
    _attr_title = "Astrion Custom Dashboard"

    def __init__(self, coordinator: AstrionCoordinator) -> None:
        """Set the unique id from the config entry."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_update"

    @property
    def installed_version(self) -> str | None:
        """Version the remote is running now."""
        return self.coordinator.data.version if self.coordinator.data else None

    @property
    def latest_version(self) -> str | None:
        """Newest published release, or the installed one when unknown.

        Falling back to installed means "no update available" rather than an
        unknown state, which is the honest reading when GitHub couldn't be
        checked — the alternative shows a permanent phantom update.
        """
        data = self.coordinator.data
        if not data:
            return None
        return data.latest_version or data.version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Ask the remote to fetch the APK and open the installer."""
        await self.coordinator.api.install_update()
