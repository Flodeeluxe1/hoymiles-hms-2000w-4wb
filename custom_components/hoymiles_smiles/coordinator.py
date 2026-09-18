"""Data coordinators for Hoymiles S-Miles Cloud."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HoymilesApi, HoymilesApiError
from .const import (
    CLOUD_POLL_SECONDS,
    CONF_INVERTER_ID,
    CONF_INVERTER_SN,
    CONF_STATION_ID,
    KEY_DAILY,
    KEY_FREQUENCY,
    KEY_MONTHLY,
    KEY_PAC,
    KEY_POWER,
    KEY_PV1,
    KEY_PV2,
    KEY_PV3,
    KEY_PV4,
    KEY_REAL_POWER,
    KEY_TEMPERATURE,
    KEY_TOTAL,
    KEY_VOLTAGE,
    KEY_YEARLY,
    REALTIME_POLL_SECONDS,
    KEY_TODAY_PROFIT,
    KEY_MONTHLY_PROFIT,
    KEY_YEARLY_PROFIT,
    KEY_TOTAL_PROFIT,
)

_LOGGER = logging.getLogger(__name__)


class HoymilesRealtimeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Near-realtime inverter coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HoymilesApi,
        station_id: int,
        inverter_sn: str,
    ) -> None:
        self.api = api
        self.station_id = station_id
        self.inverter_sn = inverter_sn

        super().__init__(
            hass,
            _LOGGER,
            name="Hoymiles realtime",
            update_interval=timedelta(seconds=REALTIME_POLL_SECONDS),
        )

    
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            online = await self.hass.async_add_executor_job(
                self.api.get_device_status,
                self.station_id,
                self.inverter_sn,
            )

            _LOGGER.warning(
                "Inverter %s online status: %s",
                self.inverter_sn,
                online,
            )

            data = await self.hass.async_add_executor_job(
                self.api.poll_realtime_burst,
                self.station_id,
                self.inverter_sn,
            )
        except Exception as err:
            _LOGGER.warning("Realtime polling failed: %s", err)
            # A failed/empty realtime channel is expected when offline.
            raise UpdateFailed(str(err)) from err

        inverter_list = data.get("mis", [])
        if not inverter_list:
            _LOGGER.debug(
                "No realtime inverter data available. "
                "The realtime URI will be refreshed on the next poll."
            )
            return { KEY_PAC: 0, KEY_PV1: 0, KEY_PV2: 0, KEY_PV3: 0, KEY_PV4: 0, }
            
        inverter = next(
            (
                item
                for item in inverter_list
                if item.get("sn") == self.inverter_sn
            ),
            inverter_list[0],
        )

        return {
            KEY_PAC: inverter.get("pac"),
            KEY_PV1: inverter.get("p1"),
            KEY_PV2: inverter.get("p2"),
            KEY_PV3: inverter.get("p3"),
            KEY_PV4: inverter.get("p4"),
        }


class HoymilesCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Five-minute station/chart coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HoymilesApi,
        station_id: int,
        inverter_id: int,
    ) -> None:
        self.api = api
        self.station_id = station_id
        self.inverter_id = inverter_id

        super().__init__(
            hass,
            _LOGGER,
            name="Hoymiles cloud",
            update_interval=timedelta(seconds=CLOUD_POLL_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            station_data, chart_data, profit_data = (
                await self.hass.async_add_executor_job(
                    self._poll_cloud,
                )
            )
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        return {
            KEY_DAILY: _to_float(station_data.get(KEY_DAILY)),
            KEY_MONTHLY: _to_float(station_data.get(KEY_MONTHLY)),
            KEY_YEARLY: _to_float(station_data.get(KEY_YEARLY)),
            KEY_TOTAL: _to_float(station_data.get(KEY_TOTAL)),
            KEY_REAL_POWER: _to_float(station_data.get(KEY_REAL_POWER)),
            KEY_POWER: chart_data.get(KEY_POWER),
            KEY_VOLTAGE: chart_data.get(KEY_VOLTAGE),
            KEY_FREQUENCY: chart_data.get(KEY_FREQUENCY),
            KEY_TEMPERATURE: chart_data.get(KEY_TEMPERATURE),
            KEY_TODAY_PROFIT: _to_float(profit_data.get(KEY_TODAY_PROFIT)),
            KEY_MONTHLY_PROFIT: _to_float(profit_data.get(KEY_MONTHLY_PROFIT)),
            KEY_YEARLY_PROFIT: _to_float(profit_data.get(KEY_YEARLY_PROFIT)),
            KEY_TOTAL_PROFIT: _to_float(profit_data.get(KEY_TOTAL_PROFIT)),
        }

    def _poll_cloud(self) -> tuple[dict[str, Any], dict[str, float]]:
        station_data = self.api.get_station_cloud_data(self.station_id)
        chart_data = self.api.get_chart_data(
            self.station_id,
            self.inverter_id,
        )
        profit_data = self.api.get_profit_data(self.station_id)
        
        return station_data, chart_data


def _to_float(value: Any) -> float | None:
    """Convert API numeric strings to float."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
