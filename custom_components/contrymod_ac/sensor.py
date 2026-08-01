"""Sensor platform for the ContryMod RV air conditioner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ContryModConfigEntry
from .entity import ContryModEntity
from .protocol import ContryModState


@dataclass(frozen=True, kw_only=True)
class ContryModSensorDescription(SensorEntityDescription):
    """Describes a ContryMod sensor."""

    value_fn: Callable[[ContryModState], float | int | None]


SENSORS: tuple[ContryModSensorDescription, ...] = (
    ContryModSensorDescription(
        key="inlet_temperature",
        translation_key="inlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.inlet_temperature,
    ),
    # The coil reading is reported in a different unit from the rest of the
    # frame. Celsius is inferred from its observed range, not confirmed.
    ContryModSensorDescription(
        key="core_temperature",
        translation_key="core_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.core_temperature,
    ),
    ContryModSensorDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda state: state.voltage,
    ),
    ContryModSensorDescription(
        key="fault_code",
        translation_key="fault_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.fault_code,
    ),
    # The app names these currents but their scaling was never confirmed --
    # both read zero in every capture -- so they are exposed unitless.
    ContryModSensorDescription(
        key="compressor_current",
        translation_key="compressor_current",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.compressor_current,
    ),
    ContryModSensorDescription(
        key="fan_current",
        translation_key="fan_current",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.fan_current,
    ),
    ContryModSensorDescription(
        key="remaining_open_time",
        translation_key="remaining_open_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.remaining_open_time,
    ),
    ContryModSensorDescription(
        key="remaining_close_time",
        translation_key="remaining_close_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.remaining_close_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ContryModConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        ContryModSensor(coordinator, description) for description in SENSORS
    )


class ContryModSensor(ContryModEntity, SensorEntity):
    """A single decoded field from the state frame."""

    entity_description: ContryModSensorDescription

    def __init__(self, coordinator, description: ContryModSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Temperatures follow whichever unit the controller reports."""
        if self.entity_description.key != "inlet_temperature":
            return self.entity_description.native_unit_of_measurement
        state = self.state_data
        if state is not None and not state.is_fahrenheit:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def native_value(self) -> float | int | None:
        state = self.state_data
        return None if state is None else self.entity_description.value_fn(state)
