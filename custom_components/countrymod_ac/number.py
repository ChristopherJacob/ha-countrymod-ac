"""Number platform for the CountryMod RV air conditioner."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CountryModConfigEntry
from .entity import CountryModEntity
from .protocol import Command


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CountryModConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the under-voltage protection setpoint."""
    async_add_entities([CountryModUnderVoltage(entry.runtime_data)])


class CountryModUnderVoltage(CountryModEntity, NumberEntity):
    """Battery cut-off voltage below which the unit stops.

    The controller offers different ranges per system voltage; the range here
    follows the 12 V system the integration was validated against.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "under_voltage"
    _attr_device_class = NumberDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_native_min_value = 9
    _attr_native_max_value = 12
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_under_voltage"

    @property
    def native_value(self) -> float | None:
        state = self.state_data
        return None if state is None else state.under_voltage

    async def async_set_native_value(self, value: float) -> None:
        # The wire value is decivolts.
        await self.coordinator.async_send_command(
            Command.UNDER_VOLTAGE, round(value) * 10
        )
