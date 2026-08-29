"""Hoymiles S-Miles Cloud integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import HoymilesApi
from .const import (
    CONF_DC,
    CONF_EMAIL,
    CONF_INVERTER_ID,
    CONF_INVERTER_SN,
    CONF_PASSWORD,
    CONF_STATION_ID,
    DOMAIN,
)
from .coordinator import HoymilesCloudCoordinator, HoymilesRealtimeCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hoymiles S-Miles Cloud from a config entry."""
    data = entry.data

    api = HoymilesApi(
        data[CONF_EMAIL],
        data[CONF_PASSWORD],
        data.get(CONF_DC, 1),
    )

    # Re-authenticate on every HA start rather than storing the API token.
    await hass.async_add_executor_job(api.login)

    realtime = HoymilesRealtimeCoordinator(
        hass,
        api,
        data[CONF_STATION_ID],
        data[CONF_INVERTER_SN],
    )
    cloud = HoymilesCloudCoordinator(
        hass,
        api,
        data[CONF_STATION_ID],
        data[CONF_INVERTER_ID],
    )

    # Realtime may legitimately be unavailable overnight. Do not fail setup
    # just because get_sd_uri is empty/offline.
    try:
        await realtime.async_config_entry_first_refresh()
    except Exception:
        pass

    try:
        await cloud.async_config_entry_first_refresh()
    except Exception:
        # Cloud data is allowed to become available on the next cycle.
        pass

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "realtime": realtime,
        "cloud": cloud,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
