"""Diagnostics for the CountryMod RV air conditioner."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import CountryModConfigEntry

TO_REDACT = {CONF_ADDRESS, "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CountryModConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    state = coordinator.data

    decoded: dict[str, Any] | None = None
    if state is not None:
        decoded = asdict(state)
        # The raw frame carries no identifiers, but hex is more useful here.
        decoded["raw"] = state.raw.hex(" ")
        decoded["under_voltage"] = state.under_voltage

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "kind_code": coordinator.kind_code,
        "last_update_success": coordinator.last_update_success,
        "state": decoded,
    }
