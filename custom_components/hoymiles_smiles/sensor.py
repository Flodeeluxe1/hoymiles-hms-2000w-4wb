"""Sensor entities for Hoymiles S-Miles Cloud."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfFrequency, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_INVERTER_ID,
    CONF_INVERTER_SN,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
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
)
from .coordinator import HoymilesCloudCoordinator, HoymilesRealtimeCoordinator


@dataclass(frozen=True)
class SensorDescription:
    """Describe a Hoymiles sensor."""

    key: str
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


REALTIME_SENSORS = (
    SensorDescription(
        KEY_PAC, "Inverter Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_PV1, "PV1 Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_PV2, "PV2 Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_PV3, "PV3 Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_PV4, "PV4 Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
)

CLOUD_SENSORS = (
    SensorDescription(
        KEY_POWER, "Cloud Inverter Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_REAL_POWER, "Station Real Power", UnitOfPower.WATT,
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_VOLTAGE, "AC Voltage", UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_FREQUENCY, "AC Frequency", UnitOfFrequency.HERTZ,
        SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_TEMPERATURE, "Inverter Temperature", UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT
    ),
    SensorDescription(
        KEY_DAILY, "Daily Energy", "kWh",
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL
    ),
    SensorDescription(
        KEY_MONTHLY, "Monthly Energy", "kWh",
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL
    ),
    SensorDescription(
        KEY_YEARLY, "Yearly Energy", "kWh",
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL
    ),
    SensorDescription(
        KEY_TOTAL, "Total Energy", "kWh",
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    realtime = data["realtime"]
    cloud = data["cloud"]

    entities: list[SensorEntity] = []

    for description in REALTIME_SENSORS:
        entities.append(
            HoymilesSensor(
                realtime,
                description,
                entry,
                "realtime",
            )
        )

    for description in CLOUD_SENSORS:
        entities.append(
            HoymilesSensor(
                cloud,
                description,
                entry,
                "cloud",
            )
        )

    async_add_entities(entities)


class HoymilesSensor(CoordinatorEntity, SensorEntity):
    """A Hoymiles sensor."""

    def __init__(
        self,
        coordinator: HoymilesRealtimeCoordinator | HoymilesCloudCoordinator,
        description: SensorDescription,
        entry: ConfigEntry,
        source: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_has_entity_name = True
        self._attr_unique_id = (
            f"{entry.entry_id}_{source}_{description.key}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{entry.data[CONF_STATION_ID]}_{entry.data[CONF_INVERTER_SN]}",
                )
            },
            name=(
                f"{entry.data[CONF_STATION_NAME]} "
                f"- {entry.data[CONF_INVERTER_SN]}"
            ),
            manufacturer="Hoymiles",
            model="S-Miles Cloud",
            serial_number=entry.data[CONF_INVERTER_SN],
            configuration_url="https://global.hoymiles.com/",
        )

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.coordinator.data.get(self.entity_description.key)
