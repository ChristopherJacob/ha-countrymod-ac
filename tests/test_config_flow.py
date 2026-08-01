"""Tests for discovery matching and the config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from custom_components.contrymod_ac.config_flow import _is_supported
from custom_components.contrymod_ac.const import DOMAIN

ADDRESS = "CA:04:59:8E:32:D5"


def service_info(name: str, uuids=(), address=ADDRESS):
    """Build a discovery record the way Home Assistant would present one.

    The controller advertises no service UUIDs at all, so the default here is
    an empty list -- matching what the radio actually sends.
    """
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-62,
        manufacturer_data={},
        service_data={},
        service_uuids=list(uuids),
        source="local",
        device=None,
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )


class TestDiscoveryMatching:
    def test_accepts_advertised_serial(self):
        assert _is_supported(service_info("KT2026020005224"))

    def test_accepts_the_gap_name(self):
        """Once anything connects, the host caches the module's GAP name.

        A controller that has ever been talked to is seen under this name
        instead of its serial, and must still be recognised.
        """
        assert _is_supported(service_info("LS Dis Server"))

    def test_is_case_insensitive(self):
        assert _is_supported(service_info("ls dis server"))
        assert _is_supported(service_info("kt2026020005224"))

    def test_rejects_unrelated_devices(self):
        assert not _is_supported(service_info("Some Other Gadget"))

    def test_rejects_missing_name(self):
        assert not _is_supported(service_info(""))

    def test_does_not_require_an_advertised_service_uuid(self):
        """The controller advertises only flags and its name.

        FFE0 exists only in the GATT table, so requiring it in the
        advertisement rejects every real controller.
        """
        assert _is_supported(service_info("KT2026020005224", uuids=()))


class TestBluetoothFlow:
    async def test_discovery_creates_entry(self, hass):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info("LS Dis Server"),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ADDRESS] == ADDRESS

    async def test_unrelated_device_is_rejected(self, hass):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info("Some Other Gadget"),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "not_supported"

    async def test_duplicate_is_rejected(self, hass):
        first = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info("LS Dis Server"),
        )
        await hass.config_entries.flow.async_configure(first["flow_id"], user_input={})
        second = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=service_info("LS Dis Server"),
        )
        assert second["type"] is FlowResultType.ABORT
        assert second["reason"] == "already_configured"


class TestManualFlow:
    async def test_lists_controllers_in_range(self, hass):
        with patch(
            "custom_components.contrymod_ac.config_flow.async_discovered_service_info",
            return_value=[service_info("LS Dis Server")],
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_ADDRESS: ADDRESS}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    @pytest.mark.parametrize(
        "discovered",
        [[], [service_info("Some Other Gadget")]],
        ids=["nothing_in_range", "only_unrelated_devices"],
    )
    async def test_aborts_when_nothing_matches(self, hass, discovered):
        with patch(
            "custom_components.contrymod_ac.config_flow.async_discovered_service_info",
            return_value=discovered,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


class TestManifestMatcher:
    """The manifest matcher is what triggers automatic discovery."""

    async def test_matcher_matches_the_real_advertisement(self, hass):
        from homeassistant.components.bluetooth.match import BluetoothMatcherIndexBase
        from homeassistant.loader import async_get_integration

        integration = await async_get_integration(hass, DOMAIN)
        index = BluetoothMatcherIndexBase()
        for matcher in integration.bluetooth:
            index.add(dict(matcher, domain=DOMAIN))
        index.build()

        # Verbatim advertisement captured from the controller: local name only.
        assert index.match(service_info("KT2026020005224"))

    async def test_matcher_ignores_unrelated_devices(self, hass):
        from homeassistant.components.bluetooth.match import BluetoothMatcherIndexBase
        from homeassistant.loader import async_get_integration

        integration = await async_get_integration(hass, DOMAIN)
        index = BluetoothMatcherIndexBase()
        for matcher in integration.bluetooth:
            index.add(dict(matcher, domain=DOMAIN))
        index.build()

        assert not index.match(service_info("Some Other Gadget"))
