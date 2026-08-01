"""Climate platform for the CountryMod RV air conditioner."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CountryModConfigEntry
from .const import DOMAIN
from .entity import CountryModEntity
from .protocol import (
    MAX_FAN_SPEED,
    MAX_TEMP_C,
    MAX_TEMP_F,
    MIN_FAN_SPEED,
    MIN_TEMP_C,
    MIN_TEMP_F,
    Command,
    ModeCommand,
    ModeState,
    Power,
    clamp_target_temperature,
)

#: Reported base mode -> Home Assistant mode.
STATE_TO_HVAC: dict[ModeState, HVACMode] = {
    ModeState.COOL: HVACMode.COOL,
    ModeState.DRY: HVACMode.DRY,
    ModeState.FAN: HVACMode.FAN_ONLY,
    ModeState.HEAT: HVACMode.HEAT,
}

#: Home Assistant mode -> the command value that selects it.
#: These differ from the values above; see the protocol contract.
HVAC_TO_COMMAND: dict[HVACMode, ModeCommand] = {
    HVACMode.COOL: ModeCommand.COOL,
    HVACMode.DRY: ModeCommand.DRY,
    HVACMode.FAN_ONLY: ModeCommand.FAN,
    HVACMode.HEAT: ModeCommand.HEAT,
}

#: Home Assistant mode -> the base mode the controller should then report.
#: Used to tell "the unit adopted the mode" from "the unit ignored it".
HVAC_TO_STATE: dict[HVACMode, ModeState] = {
    HVACMode.COOL: ModeState.COOL,
    HVACMode.DRY: ModeState.DRY,
    HVACMode.FAN_ONLY: ModeState.FAN,
    HVACMode.HEAT: ModeState.HEAT,
}

PRESET_NONE = "none"
PRESET_ECO = "eco"
PRESET_SLEEP = "sleep"
PRESET_TURBO = "turbo"
PRESET_AUTO = "auto"

PRESET_TO_COMMAND: dict[str, ModeCommand] = {
    PRESET_ECO: ModeCommand.ECO,
    PRESET_SLEEP: ModeCommand.SLEEP,
    PRESET_TURBO: ModeCommand.TURBO,
    PRESET_AUTO: ModeCommand.AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CountryModConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entity."""
    async_add_entities([CountryModClimate(entry.runtime_data)])


class CountryModClimate(CountryModEntity, ClimateEntity):
    """The air conditioner itself."""

    _attr_name = None
    _attr_translation_key = "air_conditioner"
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_AUTO,
        PRESET_ECO,
        PRESET_SLEEP,
        PRESET_TURBO,
    ]
    _attr_fan_modes = [str(speed) for speed in range(MIN_FAN_SPEED, MAX_FAN_SPEED + 1)]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_swing_modes = ["off", "on"]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.address

    # -- units -------------------------------------------------------------

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        """The controller reports which unit its own values use."""
        state = self.state_data
        if state is not None and not state.is_fahrenheit:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def min_temp(self) -> float:
        state = self.state_data
        if state is not None and not state.is_fahrenheit:
            return MIN_TEMP_C
        return MIN_TEMP_F

    @property
    def max_temp(self) -> float:
        state = self.state_data
        if state is not None and not state.is_fahrenheit:
            return MAX_TEMP_C
        return MAX_TEMP_F

    # -- state -------------------------------------------------------------

    @property
    def current_temperature(self) -> float | None:
        state = self.state_data
        return None if state is None else state.inlet_temperature

    @property
    def target_temperature(self) -> float | None:
        state = self.state_data
        return None if state is None else state.target_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        state = self.state_data
        if state is None:
            return None
        if not state.power:
            return HVACMode.OFF
        mode_state = state.mode_state
        if mode_state is None:
            # While ECO is engaged the controller reports base mode 0, which is
            # not one of its own mode values. ECO is a cooling-family preset,
            # so report COOL rather than dropping the entity to an unknown
            # mode every time ECO is selected.
            return HVACMode.COOL
        return STATE_TO_HVAC[mode_state]

    @property
    def fan_mode(self) -> str | None:
        state = self.state_data
        return None if state is None else str(state.fan_speed)

    @property
    def swing_mode(self) -> str | None:
        state = self.state_data
        return None if state is None else ("on" if state.swing else "off")

    @property
    def preset_mode(self) -> str | None:
        """Modifiers are reported as independent flags on top of the base mode."""
        state = self.state_data
        if state is None:
            return None
        if state.turbo:
            return PRESET_TURBO
        if state.eco:
            return PRESET_ECO
        if state.sleep:
            return PRESET_SLEEP
        if state.auto:
            return PRESET_AUTO
        return PRESET_NONE

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        state = self.state_data
        if state is None:
            return None
        return {
            "fault_code": state.fault_code,
            "voltage": state.voltage,
            "under_voltage_setpoint": state.under_voltage,
            "coil_temperature": state.core_temperature,
            "wind_side": "outer" if state.wind_side else "inner",
        }

    # -- commands ----------------------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        state = self.state_data
        is_fahrenheit = state is None or state.is_fahrenheit
        value = clamp_target_temperature(temperature, is_fahrenheit)
        await self.coordinator.async_send_command(Command.TARGET_TEMPERATURE, value)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode is HVACMode.OFF:
            await self.async_turn_off()
            return

        command = HVAC_TO_COMMAND.get(hvac_mode)
        if command is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_hvac_mode",
                translation_placeholders={"mode": str(hvac_mode)},
            )

        # A mode command is ignored while the unit is off, so power on first.
        state = self.state_data
        if state is not None and not state.power:
            await self.coordinator.async_send_command(Command.POWER, Power.ON)

        state = await self.coordinator.async_send_command(Command.WORK_MODE, command)

        # Not every unit implements every mode -- a cooling-only model silently
        # ignores HEAT. Surface that instead of leaving the user with a control
        # that appears to do nothing.
        if state.power and state.mode != HVAC_TO_STATE[hvac_mode]:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mode_not_accepted",
                translation_placeholders={"mode": str(hvac_mode)},
            )

    async def async_turn_on(self) -> None:
        await self.coordinator.async_send_command(Command.POWER, Power.ON)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_send_command(Command.POWER, Power.OFF)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            speed = int(fan_mode)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_fan_mode",
                translation_placeholders={"mode": fan_mode},
            ) from err
        if not MIN_FAN_SPEED <= speed <= MAX_FAN_SPEED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_fan_mode",
                translation_placeholders={"mode": fan_mode},
            )
        await self.coordinator.async_send_command(Command.FAN_SPEED, speed)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self.coordinator.async_send_command(
            Command.SWING, 1 if swing_mode == "on" else 0
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_NONE:
            # There is no "clear modifier" command; re-selecting the current
            # base mode is how the app drops back to a plain mode.
            state = self.state_data
            mode_state = None if state is None else state.mode_state
            command = (
                ModeCommand.COOL
                if mode_state is None
                else HVAC_TO_COMMAND[STATE_TO_HVAC[mode_state]]
            )
        else:
            command = PRESET_TO_COMMAND[preset_mode]
        await self.coordinator.async_send_command(Command.WORK_MODE, command)
