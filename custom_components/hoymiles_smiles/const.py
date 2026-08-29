"""Constants for the Hoymiles S-Miles Cloud integration."""

DOMAIN = "hoymiles_smiles"
NAME = "Hoymiles S-Miles Cloud"

BASE_URL = "https://euapi.hoymiles.com"
HOME_API = "https://neapi.hoymiles.com"

DEFAULT_DC = 1
USER_AGENT_TEMPLATE = "sma/ad/2.9.0/159/{dc}"

REALTIME_POLL_SECONDS = 5
CLOUD_POLL_SECONDS = 300
REQUEST_TIMEOUT = 15

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_INVERTER_ID = "inverter_id"
CONF_INVERTER_SN = "inverter_sn"
CONF_DC = "dc"

ATTR_STATION_ID = "station_id"
ATTR_INVERTER_ID = "inverter_id"
ATTR_INVERTER_SN = "inverter_sn"

KEY_PAC = "pac"
KEY_PV1 = "p1"
KEY_PV2 = "p2"
KEY_PV3 = "p3"
KEY_PV4 = "p4"

KEY_DAILY = "today_eq"
KEY_MONTHLY = "month_eq"
KEY_YEARLY = "year_eq"
KEY_TOTAL = "total_eq"
KEY_REAL_POWER = "real_power"

KEY_POWER = "MI_POWER"
KEY_VOLTAGE = "MI_NET_V"
KEY_FREQUENCY = "MI_NET_RATE"
KEY_TEMPERATURE = "MI_TEMPERATURE"
