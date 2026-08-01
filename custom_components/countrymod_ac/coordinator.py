"""Connection and refresh lifecycle for the CountryMod controller."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_SETTLE_DELAY,
    CONNECT_ATTEMPTS,
    DOMAIN,
    NOTIFY_CHAR_UUID,
    STATE_TIMEOUT,
    WRITE_CHAR_UUID,
)
from .protocol import (
    Command,
    CountryModState,
    FrameReassembler,
    build_command,
    build_query,
)

_LOGGER = logging.getLogger(__name__)


class CountryModCoordinator(DataUpdateCoordinator[CountryModState]):
    """Owns the BLE connection and serialises every exchange with the AC.

    Entities never touch the transport. They call the command helpers here,
    which pause polling, write one frame, and then confirm the result against a
    fresh state frame -- a completed write is not evidence that the controller
    acted on it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
        kind_code: int,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {address}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.address = address
        self.kind_code = kind_code
        self._client: BleakClientWithServiceCache | None = None
        self._reassembler = FrameReassembler()
        self._lock = asyncio.Lock()
        self._state_event = asyncio.Event()
        self._latest: CountryModState | None = None
        self._expected_disconnect = False

    @property
    def device_name(self) -> str:
        return self.config_entry.title if self.config_entry else self.address

    # -- transport ---------------------------------------------------------

    def _ble_device(self) -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise UpdateFailed(
                f"Controller {self.address} is not in range of any Bluetooth adapter"
            )
        return device

    def _on_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        if not self._expected_disconnect:
            _LOGGER.debug("%s disconnected unexpectedly", self.address)
        self._client = None
        self._reassembler.reset()

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        """Handle one FFE1 notification.

        Payloads are fragmented, so bytes are buffered until a whole frame is
        available.
        """
        for state in self._reassembler.add_and_decode(bytes(data)):
            self._latest = state
            self._state_event.set()

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client

        self._reassembler.reset()
        self._expected_disconnect = False
        client = await establish_connection(
            BleakClientWithServiceCache,
            self._ble_device(),
            self.device_name,
            self._on_disconnect,
            max_attempts=CONNECT_ATTEMPTS,
            use_services_cache=True,
        )
        try:
            await client.start_notify(NOTIFY_CHAR_UUID, self._on_notify)
        except (BleakError, EOFError, TimeoutError):
            await client.disconnect()
            raise

        self._client = client
        _LOGGER.debug("Connected to %s and subscribed to state", self.address)
        return client

    async def _disconnect(self) -> None:
        """Tear down the connection. The caller must hold the lock."""
        client = self._client
        self._client = None
        if client is None:
            return
        self._expected_disconnect = True
        # Best effort: the link may already be gone, which is exactly the case
        # this teardown exists to clean up after.
        with contextlib.suppress(BleakError, EOFError, TimeoutError):
            await client.stop_notify(NOTIFY_CHAR_UUID)
        with contextlib.suppress(BleakError, EOFError, TimeoutError):
            await client.disconnect()

    async def async_disconnect(self) -> None:
        """Tear down the connection, e.g. when the entry is unloaded."""
        async with self._lock:
            await self._disconnect()

    async def _write(self, frame: bytes) -> None:
        client = await self._ensure_connected()
        # Write Command (no response) is what was validated against the unit.
        await client.write_gatt_char(WRITE_CHAR_UUID, frame, response=False)

    async def _request_state(self) -> CountryModState:
        """Write a query and wait for the resulting state frame."""
        self._state_event.clear()
        await self._write(build_query(Command.REFRESH, self.kind_code))
        try:
            async with asyncio.timeout(STATE_TIMEOUT):
                await self._state_event.wait()
        except TimeoutError as err:
            # Silence after a query means the link or subscription is gone.
            await self._disconnect()
            raise UpdateFailed(
                f"Controller {self.address} did not answer a state query"
            ) from err
        assert self._latest is not None
        return self._latest

    # -- coordinator -------------------------------------------------------

    async def _async_update_data(self) -> CountryModState:
        async with self._lock:
            try:
                return await self._request_state()
            except UpdateFailed:
                raise
            except (BleakError, EOFError, TimeoutError) as err:
                await self._disconnect()
                raise UpdateFailed(
                    f"Bluetooth error talking to {self.address}: {err}"
                ) from err

    # -- commands ----------------------------------------------------------

    async def async_send_command(self, code: int, value: int) -> CountryModState:
        """Send one command and refresh state from the controller.

        Returns the state the controller reported afterwards, so callers see
        the real result rather than an optimistic guess.
        """
        async with self._lock:
            try:
                # Mirror the app: settle briefly, send one frame, then re-read.
                await asyncio.sleep(COMMAND_SETTLE_DELAY)
                await self._write(build_command(code, value, self.kind_code))
                await asyncio.sleep(COMMAND_SETTLE_DELAY)
                state = await self._request_state()
            except UpdateFailed:
                raise
            except (BleakError, EOFError, TimeoutError) as err:
                await self._disconnect()
                raise UpdateFailed(
                    f"Bluetooth error sending command to {self.address}: {err}"
                ) from err

        self.async_set_updated_data(state)
        return state
