"""Constants for the CountryMod RV air conditioner integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "countrymod_ac"

MANUFACTURER: Final = "CountryMod"
MODEL: Final = "12V/24V RV Air Conditioner (AeroLink Core)"

SERVICE_UUID: Final = "0000ffe0-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID: Final = "0000ffe2-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID: Final = "0000ffe1-0000-1000-8000-00805f9b34fb"

#: Controllers advertise their serial as the local name. FFE0 on its own is a
#: generic serial-bridge UUID, so the name is what identifies the model.
NAME_PREFIX: Final = "KT"

#: The GAP device name the module reports once anything reads it, which then
#: replaces the advertised serial in BlueZ's cache. A controller that has ever
#: been connected to is seen under this name rather than its "KT..." serial, so
#: discovery has to accept both.
GAP_NAME: Final = "LS DIS SERVER"

CONF_KIND_CODE: Final = "kind_code"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 15
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 300

#: The app waits ~300 ms after pausing its poll loop before writing a command.
COMMAND_SETTLE_DELAY: Final = 0.3

#: How long to wait for the controller to answer a query with a state frame.
STATE_TIMEOUT: Final = 8.0

#: Attempts to establish a BLE connection before giving up on one refresh.
CONNECT_ATTEMPTS: Final = 3
