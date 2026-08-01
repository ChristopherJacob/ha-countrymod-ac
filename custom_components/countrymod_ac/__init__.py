"""The CountryMod RV air conditioner integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_KIND_CODE, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import CountryModCoordinator
from .protocol import DEFAULT_KIND_CODE

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type CountryModConfigEntry = ConfigEntry[CountryModCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CountryModConfigEntry) -> bool:
    """Set up a controller from a config entry."""
    coordinator = CountryModCoordinator(
        hass,
        entry,
        address=entry.data[CONF_ADDRESS],
        kind_code=entry.data.get(CONF_KIND_CODE, DEFAULT_KIND_CODE),
        scan_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.async_disconnect()
        raise

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CountryModConfigEntry) -> bool:
    """Unload a config entry and release the Bluetooth connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_disconnect()
    return unloaded


async def _async_reload_entry(
    hass: HomeAssistant, entry: CountryModConfigEntry
) -> None:
    """Reload when options change, so the new poll interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
