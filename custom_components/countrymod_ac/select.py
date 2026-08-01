"""Select platform for the CountryMod RV air conditioner."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CountryModConfigEntry
from .entity import CountryModEntity
from .protocol import Command

WIND_SIDE_OPTIONS = ["inner", "outer"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CountryModConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the air intake selector."""
    async_add_entities([CountryModWindSide(entry.runtime_data)])


class CountryModWindSide(CountryModEntity, SelectEntity):
    """Selects recirculated (inner) or fresh (outer) intake air."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "wind_side"
    _attr_options = WIND_SIDE_OPTIONS

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_wind_side"

    @property
    def current_option(self) -> str | None:
        state = self.state_data
        return None if state is None else WIND_SIDE_OPTIONS[state.wind_side]

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_send_command(
            Command.WIND_SIDE, WIND_SIDE_OPTIONS.index(option)
        )
