"""Verify Home Assistant can discover and load this custom integration.

These reproduce what HA does at startup: read and validate the manifest, import
the component, and register its config flow. A failure here is why the
integration would not appear in the "Add integration" picker.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_custom_components, async_get_integration

from custom_components.contrymod_ac.const import DOMAIN


async def test_custom_integration_is_discovered(hass: HomeAssistant):
    custom = await async_get_custom_components(hass)
    assert DOMAIN in custom, f"not discovered; found {sorted(custom)}"


async def test_manifest_is_valid(hass: HomeAssistant):
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.config_flow is True
    assert integration.version is not None
    assert integration.bluetooth, "no bluetooth matchers declared"


async def test_component_and_config_flow_import(hass: HomeAssistant):
    integration = await async_get_integration(hass, DOMAIN)
    await integration.async_get_component()
    await integration.async_get_platform("config_flow")


async def test_all_declared_platforms_import(hass: HomeAssistant):
    integration = await async_get_integration(hass, DOMAIN)
    for platform in (
        "binary_sensor",
        "climate",
        "number",
        "select",
        "sensor",
        "switch",
        "diagnostics",
    ):
        await integration.async_get_platform(platform)


async def test_config_flow_is_offered_to_users(hass: HomeAssistant):
    """This is exactly what populates the Add integration picker."""
    from homeassistant.generated.config_flows import FLOWS
    from homeassistant.loader import async_get_config_flows

    flows = await async_get_config_flows(hass)
    assert DOMAIN in flows, (
        f"{DOMAIN} not offered as a config flow; "
        f"core flows={len(FLOWS.get('integration', []))}"
    )
