"""Sensor entities for Hoymiles S-Miles Cloud."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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


SensorDescription = SensorEntityDescription

REALTIME_SENSORS = (
    SensorDescription(
        key=KEY_PAC,
        name="Inverter Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_PV1,
        name="PV1 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_PV2,
        name="PV2 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_PV3,
        name="PV3 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_PV4,
        name="PV4 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

CLOUD_SENSORS = (
    SensorDescription(
        key=KEY_POWER,
        name="Cloud Inverter Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_REAL_POWER,
        name="Station Real Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_VOLTAGE,
        name="AC Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_FREQUENCY,
        name="AC Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_TEMPERATURE,
        name="Inverter Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDescription(
        key=KEY_DAILY,
        name="Daily Energy",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDescription(
        key=KEY_MONTHLY,
        name="Monthly Energy",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDescription(
        key=KEY_YEARLY,
        name="Yearly Energy",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDescription(
        key=KEY_TOTAL,
        name="Total Energy",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
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
