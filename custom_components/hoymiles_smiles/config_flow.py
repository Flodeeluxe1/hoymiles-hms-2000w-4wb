"""Config flow for Hoymiles S-Miles Cloud."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback

from .api import HoymilesApi, HoymilesApiError
from .const import (
    CONF_DC,
    CONF_INVERTER_ID,
    CONF_INVERTER_SN,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_DC,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("dc", default=DEFAULT_DC): vol.Coerce(int),
    }
)


class HoymilesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hoymiles S-Miles Cloud config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api: HoymilesApi | None = None
        self._stations: list[dict[str, Any]] = []
        self._inverters: list[dict[str, Any]] = []
        self._user_data: dict[str, Any] = {}
        self._station: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Ask for S-Miles credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api = HoymilesApi(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    user_input.get("dc", DEFAULT_DC),
                )
                await self.hass.async_add_executor_job(api.login)
                stations = await self.hass.async_add_executor_job(
                    api.get_stations
                )

                if not stations:
                    errors["base"] = "no_stations"
                else:
                    self._api = api
                    self._stations = stations
                    self._user_data = {
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_DC: user_input.get("dc", DEFAULT_DC),
                    }
                    return await self.async_step_station()

            except (HoymilesApiError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_station(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Select a station."""
        if user_input is not None:
            station_id = int(user_input["station_id"])
            self._station = next(
                station
                for station in self._stations
                if int(station.get("id")) == station_id
            )

            assert self._api is not None
            device_tree = await self.hass.async_add_executor_job(
                self._api.get_device_tree,
                station_id,
            )
            self._inverters = self._api.get_inverters(device_tree)

            if not self._inverters:
                return self.async_abort(reason="no_inverters")

            return await self.async_step_inverter()

        station_options = {
            str(station["id"]): station.get("name") or str(station["id"])
            for station in self._stations
        }

        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "station_id",
                    ): vol.In(station_options)
                }
            ),
        )

    async def async_step_inverter(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Select an inverter."""
        if user_input is not None:
            inverter_id = int(user_input["inverter_id"])
            inverter = next(
                inv
                for inv in self._inverters
                if int(inv.get("id")) == inverter_id
            )

            station_id = int(self._station["id"])
            station_name = self._station.get("name") or str(station_id)

            await self.async_set_unique_id(
                f"{station_id}_{inverter.get('sn')}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"{station_name} - {inverter.get('sn')}",
                data={
                    **self._user_data,
                    CONF_STATION_ID: station_id,
                    CONF_STATION_NAME: station_name,
                    CONF_INVERTER_ID: int(inverter["id"]),
                    CONF_INVERTER_SN: inverter["sn"],
                    CONF_DC: self._user_data.get(CONF_DC, DEFAULT_DC),
                },
            )

        inverter_options = {
            str(inv["id"]): f"{inv.get('sn')} ({inv.get('type', 'inverter')})"
            for inv in self._inverters
        }

        return self.async_show_form(
            step_id="inverter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "inverter_id",
                    ): vol.In(inverter_options)
                }
            ),
        )

