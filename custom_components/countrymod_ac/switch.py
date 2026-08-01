"""Switch platform for the CountryMod RV air conditioner."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
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
    """Set up the panel display and light switches."""
    async_add_entities(
        [
            CountryModScreenDisplay(entry.runtime_data),
            CountryModLight(entry.runtime_data),
        ]
    )


class CountryModScreenDisplay(CountryModEntity, SwitchEntity):
    """The controller's own panel display."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "screen_display"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_screen_display"

    @property
    def is_on(self) -> bool | None:
        state = self.state_data
        return None if state is None else state.screen_display

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(Command.SCREEN_DISPLAY, 2)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(Command.SCREEN_DISPLAY, 1)


class CountryModLight(CountryModEntity, SwitchEntity):
    """The controller's ambient light.

    The vendor app cycles this through three values, but the controller only
    reports one bit, and value 2 reads back as off -- so it is modelled as a
    plain switch.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "light"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_light"

    @property
    def is_on(self) -> bool | None:
        state = self.state_data
        return None if state is None else state.light

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(Command.LIGHT, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(Command.LIGHT, 0)
