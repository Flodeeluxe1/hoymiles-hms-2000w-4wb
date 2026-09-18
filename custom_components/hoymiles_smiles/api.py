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
    LOGGER.debug("Creating chart protobuf class.")

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

    LOGGER.debug("Chart protobuf class created.")

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

        LOGGER.debug(
            "API client initialized. DC=%s, email=%s",
            dc,
            email,
        )

    @property
    def headers(self) -> dict[str, str]:
        """Return API request headers."""
        return {
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
            "Authorization": self.token or "",
        }

    ```python
    def _post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        _retry: bool = True,
    ) -> requests.Response:
        """Send a POST request and retry once after token expiration."""
        LOGGER.debug("POST request to %s", url)

        try:
            response = requests.post(
                url,
                headers=headers or self.headers,
                json=json_data,
                timeout=REQUEST_TIMEOUT,
            )

            LOGGER.debug(
                "HTTP response %s from %s",
                response.status_code,
                url,
            )

            response.raise_for_status()

            # Hoymiles can return HTTP 200 even when the authentication
            # token has expired. Detect that from the API response.
            try:
                result = response.json()
            except ValueError:
                result = None

            if (
                _retry
                and isinstance(result, dict)
                and result.get("status") == "100"
                and result.get("message") == "token verify error"
            ):
                LOGGER.warning(
                    "Hoymiles token has expired. Re-authenticating and retrying request."
                )

                self.login()

                return self._post(
                    url,
                    headers=headers,
                    json_data=json_data,
                    _retry=False,
                )

            return response

        except Exception as err:
            LOGGER.warning(
                "POST failed for %s: %s",
                url,
                err,
            )
            raise
```


    def login(self) -> None:
        """Authenticate using the S-Miles Argon2id challenge."""
        LOGGER.debug("Starting login.")

        pre_url = BASE_URL + "/iam/pub/3/auth/pre-insp"
        base_headers = {
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

        LOGGER.debug("Requesting authentication challenge.")

        response = self._post(
            pre_url,
            headers=base_headers,
            json_data={"u": self.email},
        )
        pre = response.json()

        LOGGER.debug(
            "Authentication challenge status=%s",
            pre.get("status"),
        )

        if pre.get("status") != "0":
            raise HoymilesApiError(
                f"Authentication challenge failed: {pre.get('message', pre)}"
            )

        challenge = pre["data"]
        nonce = challenge["n"]
        salt_hex = challenge["a"]

        LOGGER.debug("Authentication challenge received.")

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

        LOGGER.debug("Argon2id hash calculated.")

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

        LOGGER.debug(
            "Login response status=%s",
            login.get("status"),
        )

        if login.get("status") != "0":
            raise HoymilesApiError(
                f"Login failed: {login.get('message', login)}"
            )

        token = login.get("data", {}).get("token")

        if not token:
            LOGGER.warning(
                "Login succeeded but no token was returned."
            )
            raise HoymilesApiError(
                "Login succeeded but no token was returned."
            )

        self.token = token

        LOGGER.debug("Login successful. Token received.")

    def get_stations(self) -> list[dict[str, Any]]:
        """Return the account's stations."""
        LOGGER.debug("Requesting stations.")

        url = HOME_API + "/pvm/api/0/station/select_by_page"

        response = self._post(
            url,
            json_data={"page": 1, "page_size": 50},
        )
        result = response.json()

        LOGGER.debug(
            "Station response status=%s",
            result.get("status"),
        )

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Station request failed: {result.get('message', result)}"
            )

        stations = result.get("data", {}).get("list", [])

        LOGGER.debug(
            "%s station(s) returned.",
            len(stations),
        )

        return stations

    def get_device_tree(self, station_id: int) -> list[dict[str, Any]]:
        """Return DTUs and inverters for a station."""
        LOGGER.debug(
            "Requesting device tree for station_id=%s.",
            station_id,
        )

        url = HOME_API + "/pvmc/api/0/station/select_device_c"

        response = self._post(
            url,
            json_data={"sid": station_id},
        )
        result = response.json()

        LOGGER.debug(
            "Device tree response status=%s.",
            result.get("status"),
        )

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Device tree request failed: {result.get('message', result)}"
            )

        devices = result.get("data", [])

        LOGGER.debug(
            "Device tree returned %s top-level device(s).",
            len(devices),
        )

        return devices


    def get_device_status(
        self,
        station_id: int,
        inverter_sn: str,
    ) -> bool | None:
        """Return the inverter online status.

        Returns True when the inverter is connected, False when it is
        disconnected, or None when the inverter cannot be found.
        """
        LOGGER.debug(
            "Requesting device status for station_id=%s inverter_sn=%s.",
            station_id,
            inverter_sn,
        )

        url = HOME_API + "/pvm/api/0/station/select_device_of_tree"

        response = self._post(
            url,
            json_data={"id": station_id},
        )
        result = response.json()

        LOGGER.debug(
            "Device status response status=%s.",
            result.get("status"),
        )

        if result.get("status") != "0":
            raise HoymilesApiError(
                "Device status request failed: "
                f"{result.get('message', result)}"
            )

        for dtu in result.get("data", []):
            for inverter in dtu.get("children", []):
                if inverter.get("sn") == inverter_sn:
                    warn_data = inverter.get("warn_data", {})
                    connected = warn_data.get("connect")

                    LOGGER.debug(
                        "Inverter %s connection status=%s.",
                        inverter_sn,
                        connected,
                    )

                    if isinstance(connected, bool):
                        return connected

                    LOGGER.warning(
                        "Inverter %s returned an invalid connection status.",
                        inverter_sn,
                    )
                    return None

        LOGGER.warning(
            "Inverter %s was not found in device status response.",
            inverter_sn,
        )
        return None


    @staticmethod
    def get_inverters(
        device_tree: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract inverters from the device tree."""
        LOGGER.debug("Extracting inverters from device tree.")

        inverters: list[dict[str, Any]] = []

        for dtu in device_tree:
            for inverter in dtu.get("devices", []):
                if inverter.get("id") and inverter.get("sn"):
                    inverters.append(inverter)

        LOGGER.debug(
            "Found %s inverter(s).",
            len(inverters),
        )

        return inverters

    def get_realtime_uri(self, station_id: int) -> str:
        """Request a fresh short-lived realtime URI."""
        LOGGER.debug(
            "Requesting fresh realtime URI for station_id=%s.",
            station_id,
        )

        url = HOME_API + "/pvm/api/0/station/get_sd_uri"

        try:
            response = self._post(
                url,
                json_data={"sid": station_id},
            )
            result = response.json()

            LOGGER.debug(
                "get_sd_uri response status=%s.",
                result.get("status"),
            )

            if result.get("status") != "0":
                LOGGER.warning(
                    "get_sd_uri failed: %s",
                    result.get("message", result),
                )
                raise HoymilesApiError(
                    f"get_sd_uri failed: {result.get('message', result)}"
                )

            uri = result.get("data", {}).get("uri", "") or ""

            self.realtime_uri = uri

            if uri:
                LOGGER.debug(
                    "Fresh realtime URI received successfully."
                )
            else:
                LOGGER.warning(
                    "get_sd_uri returned an EMPTY URI."
                )

            return uri

        except Exception as err:
            LOGGER.warning(
                "Exception while requesting realtime URI: %s",
                err,
            )
            raise

    def poll_realtime_burst(
        self,
        station_id: int,
        inverter_sn: str,
    ) -> dict[str, Any]:
        """Request m=3 inverter realtime data."""
        LOGGER.debug(
            "Starting realtime poll. "
            "station_id=%s inverter_sn=%s URI_present=%s",
            station_id,
            inverter_sn,
            bool(self.realtime_uri),
        )

        if not self.realtime_uri:
            LOGGER.debug(
                "No realtime URI available. Requesting a new one."
            )
            self.get_realtime_uri(station_id)

        if not self.realtime_uri:
            LOGGER.warning(
                "Realtime URI is EMPTY after get_realtime_uri()."
            )
            raise HoymilesApiError(
                "get_sd_uri returned an empty URI. "
                "The inverter/DTU may currently be offline."
            )

        LOGGER.debug("Sending realtime burst request.")

        try:
            response = self._post(
                self.realtime_uri,
                json_data={
                    "m": 3,
                    "mis": [inverter_sn],
                    "t": 1,
                },
            )

            LOGGER.debug(
                "Realtime burst HTTP request completed."
            )

            result = response.json()

            LOGGER.debug(
                "Realtime API response: %s",
                result,
            )

            status = result.get("status")
            data = result.get("data", {})
            inverter_list = data.get("mis", [])

            LOGGER.debug(
                "Realtime status=%s, data_keys=%s, "
                "inverter_count=%s, dly=%s.",
                status,
                list(data.keys()) if isinstance(data, dict) else None,
                len(inverter_list),
                data.get("dly") if isinstance(data, dict) else None,
            )

            if status != "0":
                LOGGER.warning(
                    "Realtime burst returned non-zero status: %s",
                    status,
                )
                raise HoymilesApiError(
                    f"Realtime burst failed: {result.get('message', result)}"
                )

            if not inverter_list:
                LOGGER.warning(
                    "Realtime response contains no inverter data. "
                    "Clearing realtime URI so the next poll requests a fresh URI."
                )
                self.realtime_uri = ""

            else:
                LOGGER.debug(
                    "Realtime inverter data received for %s inverter(s).",
                    len(inverter_list),
                )

            return data

        except Exception as err:
            LOGGER.warning(
                "Exception during realtime burst: %s",
                err,
            )

            LOGGER.warning(
                "Clearing realtime URI because realtime request failed."
            )

            self.realtime_uri = ""
            raise

    def get_station_cloud_data(
        self,
        station_id: int,
    ) -> dict[str, Any]:
        """Return station daily/monthly/yearly/total energy and real power."""
        LOGGER.debug(
            "Requesting station cloud data for station_id=%s.",
            station_id,
        )

        url = HOME_API + "/pvmc/api/0/station_data/count_station_real_data_c"

        response = self._post(
            url,
            json_data={"sid": station_id},
        )
        result = response.json()

        LOGGER.debug(
            "Station cloud response status=%s.",
            result.get("status"),
        )

        if result.get("status") != "0":
            raise HoymilesApiError(
                f"Station cloud request failed: {result.get('message', result)}"
            )

        data = result.get("data", {})

        LOGGER.debug(
            "Station cloud data keys=%s.",
            list(data.keys()),
        )

        return data

    def get_chart_data(
        self,
        station_id: int,
        inverter_id: int,
    ) -> dict[str, float]:
        """Return the last positive values from the inverter LineChart."""
        from datetime import datetime

        LOGGER.debug(
            "Requesting chart data. "
            "station_id=%s inverter_id=%s.",
            station_id,
            inverter_id,
        )

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

        response = self._post(
            url,
            json_data=body,
        )

        raw_chart = response.content

        LOGGER.debug(
            "Chart response received. %s bytes.",
            len(raw_chart),
        )

        if not raw_chart:
            LOGGER.warning("Chart response is EMPTY.")
            return {}

        try:
            chart = LineChart()
            chart.ParseFromString(raw_chart)

            LOGGER.debug(
                "Chart protobuf parsed. series_count=%s.",
                len(chart.series),
            )

        except Exception as err:
            LOGGER.warning(
                "Chart protobuf parsing failed: %s",
                err,
            )
            raise

        result: dict[str, float] = {}

        for series in chart.series:
            values = list(series.data)

            LOGGER.debug(
                "Chart series type=%s values=%s.",
                series.type,
                len(values),
            )

            if not values:
                continue

            last_positive = None

            for value in reversed(values):
                if value > 0:
                    last_positive = round(float(value), 1)
                    break

            if last_positive is not None:
                result[series.type] = last_positive

        LOGGER.debug(
            "Chart data extracted: %s",
            result,
        )

        return result
