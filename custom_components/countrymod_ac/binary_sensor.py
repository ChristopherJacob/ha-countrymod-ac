"""Binary sensor platform for the CountryMod RV air conditioner."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CountryModConfigEntry
from .entity import CountryModEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CountryModConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fault indicator."""
    async_add_entities([CountryModProblem(entry.runtime_data)])


class CountryModProblem(CountryModEntity, BinarySensorEntity):
    """Reports a non-zero fault code from the controller."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "problem"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_problem"

    @property
    def is_on(self) -> bool | None:
        state = self.state_data
        return None if state is None else state.has_fault
