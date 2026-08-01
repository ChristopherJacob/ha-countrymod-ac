"""Shared entity base for the CountryMod integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import CountryModCoordinator
from .protocol import CountryModState


class CountryModEntity(CoordinatorEntity[CountryModCoordinator]):
    """Base entity bound to one controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CountryModCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def state_data(self) -> CountryModState | None:
        """Latest decoded state, or None while the controller is unreachable."""
        return self.coordinator.data

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
