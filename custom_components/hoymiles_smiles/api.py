"""Synchronous S-Miles Cloud API client.

The HTTP/API calls intentionally stay close to the proven Colab implementation.
Home Assistant calls this client from executor jobs so requests do not block
the Home Assistant event loop.
"""


from __future__ import annotations

import logging

from typing import Any

import requests
from argon2.low_level import Type, hash_secret_raw
from google.protobuf import descriptor_pb2
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.message_factory import GetMessageClass

from .const import (
    BASE_URL,
    HOME_API,
    REQUEST_TIMEOUT,
    USER_AGENT_TEMPLATE,
)


class HoymilesApiError(Exception):
    """Raised when the S-Miles API returns an error."""

LOGGER = logging.getLogger(__name__)


def create_chart_proto_class():
    """Create the LineChart protobuf class used by the chart endpoint."""
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "Chart.proto"
    file_proto.syntax = "proto3"

    line_series = file_proto.message_type.add()
    line_series.name = "LineSeries"

    field = line_series.field.add()
    field.name = "type"
    field.number = 1
    field.label = 1
    field.type = 9

    field = line_series.field.add()
    field.name = "data"
    field.number = 2
    field.label = 3
    field.type = 2

    field = line_series.field.add()
    field.name = "did"
    field.number = 3
    field.label = 1
    field.type = 5

    field = line_series.field.add()
    field.name = "port"
    field.number = 4
    field.label = 1
    field.type = 5

    line_chart = file_proto.message_type.add()
    line_chart.name = "LineChart"

    field = line_chart.field.add()
    field.name = "x_axis"
    field.number = 1
    field.label = 3
    field.type = 9

    field = line_chart.field.add()
    field.name = "series"
    field.number = 2
    field.label = 3
    field.type = 11
    field.type_name = ".LineSeries"

    field = line_chart.field.add()
    field.name = "type"
    field.number = 3
    field.label = 1
    field.type = 9

    pool = DescriptorPool()
    pool.Add(file_proto)
    descriptor = pool.FindMessageTypeByName("LineChart")
    return GetMessageClass(descriptor)


LineChart = create_chart_proto_class()


class HoymilesApi:
    """S-Miles Cloud API client."""

    def __init__(self, email: str, password: str, dc: int = 1) -> None:
        self.email = email
        self.password = password
        self.dc = dc
        self.user_agent = USER_AGENT_TEMPLATE.format(dc=dc)
        self.token: str | None = None
        self.realtime_uri: str = ""

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
            "Authorization": self.token or "",
        }

    def _post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> requests.Response:
        response = requests.post(
            url,
            headers=headers or self.headers,
            json=json_data,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response

    def login(self) -> None:
        """Authenticate using the S-Miles Argon2id challenge."""
        pre_url = BASE_URL + "/iam/pub/3/auth/pre-insp"
        base_headers = {
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

        response = self._post(
            pre_url,
            headers=base_headers,
            json_data={"u": self.email},
        )
        pre = response.json()

        if pre.get("status") != "0":
            raise HoymilesApiError(
                f"Authentication challenge failed: {pre.get('message', pre)}"
            )

        challenge = pre["data"]
        nonce = challenge["n"]
        salt_hex = challenge["a"]

        argon_hash = hash_secret_raw(
            secret=self.password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            time_cost=3,
            memory_cost=32768,
            parallelism=1,
            hash_len=32,
            type=Type.ID,
            version=0x13,
        )

        login_url = BASE_URL + "/iam/pub/3/auth/login"
        response = self._post(
            login_url,
            headers=base_headers,
            json_data={
                "u": self.email,
                "ch": argon_hash.hex(),
                "n": nonce,
            },
        )
        login = response.json()

        if login.get("status") != "0":
            raise HoymilesApiError(
                f"Login failed: {login.get('message', login)}"
            )

        token = login.get("data", {}).get("token")
        if not token:
            raise HoymilesApiError("Login succeeded but no token was returned.")

        self.token = token

    def get_stations(self) -> list[dict[str, Any]]:
        """Return the account's stations."""
        url = HOME_API + "/pvm/api/0/station/select_by_page"
        response = self._post(
            url,
            json_data={"page": 1, "page_size": 50},
        )
        result = response.json()

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Station request failed: {result.get('message', result)}"
            )

        return result.get("data", {}).get("list", [])

    def get_device_tree(self, station_id: int) -> list[dict[str, Any]]:
        """Return DTUs and inverters for a station."""
        url = HOME_API + "/pvmc/api/0/station/select_device_c"
        response = self._post(url, json_data={"sid": station_id})
        result = response.json()

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Device tree request failed: {result.get('message', result)}"
            )

        return result.get("data", [])

    @staticmethod
    def get_inverters(
        device_tree: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract inverters from the device tree."""
        inverters: list[dict[str, Any]] = []
        for dtu in device_tree:
            for inverter in dtu.get("devices", []):
                if inverter.get("id") and inverter.get("sn"):
                    inverters.append(inverter)
        return inverters

    def get_realtime_uri(self, station_id: int) -> str:
        """Request a fresh short-lived realtime URI."""
        url = HOME_API + "/pvm/api/0/station/get_sd_uri"
        response = self._post(url, json_data={"sid": station_id})
        result = response.json()

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"get_sd_uri failed: {result.get('message', result)}"
            )

        uri = result.get("data", {}).get("uri", "") or ""
        self.realtime_uri = uri
        return uri


def poll_realtime_burst(
    self,
    station_id: int,
    inverter_sn: str,
) -> dict[str, Any]:
    """Request m=3 inverter realtime data."""
    if not self.realtime_uri:
        self.get_realtime_uri(station_id)

    if not self.realtime_uri:
        raise HoymilesApiError(
            "get_sd_uri returned an empty URI. "
            "The inverter/DTU may currently be offline."
        )

    try:
        response = self._post(
            self.realtime_uri,
            json_data={
                "m": 3,
                "mis": [inverter_sn],
                "t": 1,
            },
        )
        result = response.json()

        LOGGER.warning("Realtime API response: %s", result)

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Realtime burst failed: {result.get('message', result)}"
            )

        data = result.get("data", {})

        # The realtime URI can expire without returning an API error.
        # In that case Hoymiles returns data without the "mis" array.
        if not data.get("mis"):
            LOGGER.warning(
                "Realtime URI appears to be expired. Requesting a fresh URI."
            )

            self.realtime_uri = ""
            self.get_realtime_uri(station_id)

            if not self.realtime_uri:
                raise HoymilesApiError(
                    "get_sd_uri returned an empty URI after realtime URI expired."
                )

            response = self._post(
                self.realtime_uri,
                json_data={
                    "m": 3,
                    "mis": [inverter_sn],
                    "t": 1,
                },
            )
            result = response.json()

            LOGGER.warning("Realtime API response after URI refresh: %s", result)

            if result.get("status") != "0":
                raise HoymilesApiError(
                    "Realtime burst failed after URI refresh: "
                    f"{result.get('message', result)}"
                )

            return result.get("data", {})

        return data

    except Exception:
        # Clear the URI so the next polling cycle obtains a fresh one.
        self.realtime_uri = ""
        raise


    def get_station_cloud_data(
        self,
        station_id: int,
    ) -> dict[str, Any]:
        """Return station daily/monthly/yearly/total energy and real power."""
        url = HOME_API + "/pvmc/api/0/station_data/count_station_real_data_c"
        response = self._post(url, json_data={"sid": station_id})
        result = response.json()

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Station cloud request failed: {result.get('message', result)}"
            )

        return result.get("data", {})

    def get_chart_data(
        self,
        station_id: int,
        inverter_id: int,
    ) -> dict[str, float]:
        """Return the last positive values from the inverter LineChart."""
        from datetime import datetime

        url = HOME_API + "/pvmc/api/0/micro_data/count_by_day_c"
        body = {
            "sid": station_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "mi_list": [inverter_id],
            "quota": [
                "MI_POWER",
                "MI_NET_V",
                "MI_NET_RATE",
                "MI_TEMPERATURE",
            ],
        }

        response = self._post(url, json_data=body)
        raw_chart = response.content

        if not raw_chart:
            return {}

        chart = LineChart()
        chart.ParseFromString(raw_chart)

        result: dict[str, float] = {}
        for series in chart.series:
            values = list(series.data)
            if not values:
                continue

            last_positive = None
            for value in reversed(values):
                if value > 0:
                    last_positive = round(float(value), 1)
                    break

            if last_positive is not None:
                result[series.type] = last_positive

        return result
