"""Sensor platform for HomGar integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Generic, TypeVar, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HomgarDataUpdateCoordinator
from .const import DOMAIN
from .entity import HomgarBaseEntity
from .homgarapi.devices import (
    HomgarDevice,
    HomgarHubDevice,
    RainPointAirSensor,
    RainPointCO2Sensor,
    RainPointDisplayHub,
    RainPointGatewayHub,
    RainPointPoolSensor,
    RainPointRainSensor,
    RainPointSoilMoistureSensor,
)

_LOGGER = logging.getLogger(__name__)


def _log_sensor_debug(unique_id: str, message: str, *args: Any) -> None:
    """Log a sensor-scoped debug message."""
    if _LOGGER.isEnabledFor(logging.DEBUG):
        formatted = message % args if args else message
        _LOGGER.debug("Sensor %s: %s", unique_id, formatted)


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "temperature_max": SensorEntityDescription(
        key="temperature_max",
        translation_key="temperature_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "temperature_min": SensorEntityDescription(
        key="temperature_min",
        translation_key="temperature_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "humidity_max": SensorEntityDescription(
        key="humidity_max",
        translation_key="humidity_max",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "humidity_min": SensorEntityDescription(
        key="humidity_min",
        translation_key="humidity_min",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "co2": SensorEntityDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "co2_min": SensorEntityDescription(
        key="co2_min",
        translation_key="co2_min",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "co2_max": SensorEntityDescription(
        key="co2_max",
        translation_key="co2_max",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "co2_alert": SensorEntityDescription(
        key="co2_alert",
        translation_key="co2_alert",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
    ),
    "soil_moisture": SensorEntityDescription(
        key="soil_moisture",
        translation_key="soil_moisture",
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "light": SensorEntityDescription(
        key="light",
        translation_key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    "rainfall_total": SensorEntityDescription(
        key="rainfall_total",
        translation_key="rainfall_total",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    "rainfall_hourly": SensorEntityDescription(
        key="rainfall_hourly",
        translation_key="rainfall_hourly",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mm/h",
    ),
    "rainfall_daily": SensorEntityDescription(
        key="rainfall_daily",
        translation_key="rainfall_daily",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    "rainfall_weekly": SensorEntityDescription(
        key="rainfall_weekly",
        translation_key="rainfall_weekly",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    "rssi": SensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery_state": SensorEntityDescription(
        key="battery_state",
        translation_key="battery_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "pool_water_temp": SensorEntityDescription(
        key="pool_water_temperature",
        translation_key="pool_water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "pool_water_temp_max": SensorEntityDescription(
        key="pool_water_temperature_max",
        translation_key="pool_water_temperature_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "pool_water_temp_min": SensorEntityDescription(
        key="pool_water_temperature_min",
        translation_key="pool_water_temperature_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "last_seen": SensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


def create_rf_rssi_description() -> SensorEntityDescription:
    """Create RF RSSI sensor description."""
    return SensorEntityDescription(
        key="rf_rssi",
        translation_key="rf_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
    )


def create_wifi_rssi_description() -> SensorEntityDescription:
    """Create WiFi RSSI sensor description."""
    return SensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
    )


def _attribute_getter(attribute: str) -> Callable[[Any], Any]:
    """Return a callable that fetches an attribute from a device."""

    def getter(device: Any) -> Any:
        return getattr(device, attribute)

    return getter


def _get_description(key: str) -> SensorEntityDescription | None:
    """Safely fetch a sensor description by key."""
    description = SENSOR_DESCRIPTIONS.get(key)
    if description is None:
        fallback_map: dict[str, SensorEntityDescription] = {
            "humidity": SensorEntityDescription(
                key="humidity",
                translation_key="humidity",
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
            ),
            "battery": SensorEntityDescription(
                key="battery",
                translation_key="battery",
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "light": SensorEntityDescription(
                key="light",
                translation_key="light",
                device_class=SensorDeviceClass.ILLUMINANCE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=LIGHT_LUX,
            ),
            "battery_state": SensorEntityDescription(
                key="battery_state",
                translation_key="battery_state",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "pool_water_temp": SensorEntityDescription(
                key="pool_water_temperature",
                translation_key="pool_water_temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            ),
        }
        if key in fallback_map:
            description = fallback_map[key]
            SENSOR_DESCRIPTIONS[key] = description
            _LOGGER.warning(
                "Missing sensor description for key '%s', using fallback definition",
                key,
            )
        else:
            _LOGGER.warning("Missing sensor description for key '%s'", key)
    return description


DeviceT = TypeVar("DeviceT")


@dataclass(frozen=True)
class SensorSpec(Generic[DeviceT]):
    """Configuration describing how to obtain a sensor value."""

    attr_name: str | None = None
    value_fn: Callable[[DeviceT], Any] | None = None
    allow_none: bool = True
    requires_attribute: bool = True

    @classmethod
    def from_attribute(
        cls,
        attr_name: str,
        *,
        allow_none: bool = True,
        requires_attribute: bool = True,
    ) -> SensorSpec[DeviceT]:
        """Create a spec that reads from a device attribute."""
        return cls(
            attr_name=attr_name,
            allow_none=allow_none,
            requires_attribute=requires_attribute,
        )

    @classmethod
    def from_callable(
        cls,
        value_fn: Callable[[DeviceT], Any],
        *,
        allow_none: bool = True,
    ) -> SensorSpec[DeviceT]:
        """Create a spec that uses a custom callable for values."""
        return cls(
            value_fn=value_fn,
            allow_none=allow_none,
            requires_attribute=False,
        )

    def build_value_fn(self) -> Callable[[DeviceT], Any]:
        """Return the callable that should supply sensor values."""
        if self.value_fn is not None:
            return self.value_fn
        if self.attr_name is None:
            msg = "SensorSpec requires either attr_name or value_fn"
            raise ValueError(msg)
        getter = _attribute_getter(self.attr_name)
        return cast(Callable[[DeviceT], Any], getter)

    def should_add(self, device: DeviceT) -> bool:
        """Return True when the sensor should be created for the device."""
        if self.requires_attribute:
            if self.attr_name is None:
                msg = "SensorSpec requires attr_name when requires_attribute is True"
                raise ValueError(msg)
            if not hasattr(device, self.attr_name):
                return False
            try:
                attr_value = getattr(device, self.attr_name)
            except AttributeError:
                return False
            if attr_value is None and not self.allow_none:
                return False
        elif not self.allow_none:
            value_getter = self.build_value_fn()
            try:
                candidate_value = value_getter(device)
            except (AttributeError, TypeError, ValueError):
                return False
            if candidate_value is None:
                return False
        return True


def create_sensor_if_exists(
    sensors: list[HomgarSensor],
    coordinator: HomgarDataUpdateCoordinator,
    device: DeviceT,
    description: SensorEntityDescription,
    spec: SensorSpec[DeviceT],
) -> None:
    """Helper to create sensor if the spec deems it available."""
    supports_sensor = getattr(device, "supports_sensor", lambda key: True)
    if not supports_sensor(description.key):
        return

    if not spec.should_add(device):
        return

    value_fn = cast(Callable[[Any], Any], spec.build_value_fn())
    sensors.append(
        HomgarSensor(
            coordinator,
            device,
            description,
            value_fn,
        )
    )


def add_common_sensors(
    sensors: list[HomgarSensor],
    coordinator: HomgarDataUpdateCoordinator,
    device: Any,
    *,
    include_temperature: bool = True,
    include_humidity: bool = True,
) -> None:
    """Add common sensors that appear on multiple device types."""

    # Temperature sensor (common pattern)
    if (
        include_temperature
        and getattr(device, "temperature_c", None) is not None
        and (description := _get_description("temperature"))
    ):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[HomgarDevice].from_callable(
                lambda dev: cast(float | None, getattr(dev, "temperature_c", None))
            ),
        )

    # Humidity sensor (common pattern)
    if (
        include_humidity
        and getattr(device, "humidity_pct", None) is not None
        and (description := _get_description("humidity"))
    ):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[HomgarDevice].from_callable(
                lambda dev: cast(int | None, getattr(dev, "humidity_pct", None))
            ),
        )

    # RF RSSI sensor (common pattern)
    create_sensor_if_exists(
        sensors,
        coordinator,
        device,
        create_rf_rssi_description(),
        SensorSpec[HomgarDevice].from_attribute("rf_rssi", allow_none=False),
    )

    # Battery sensor (common pattern)
    if description := _get_description("battery"):
        if getattr(device, "HAS_BATTERY", True):
            create_sensor_if_exists(
                sensors,
                coordinator,
                device,
                description,
                SensorSpec[HomgarDevice].from_attribute("battery_level"),
            )
    if description := _get_description("battery_state"):
        if getattr(device, "HAS_BATTERY", True):
            create_sensor_if_exists(
                sensors,
                coordinator,
                device,
                description,
                SensorSpec[HomgarDevice].from_attribute("battery_state"),
            )
    if (description := _get_description("last_seen")) and getattr(
        device, "last_seen", None
    ):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[HomgarDevice].from_callable(
                lambda dev: dt_util.parse_datetime(str(dev.last_seen))
                if getattr(dev, "last_seen", None)
                else None
            ),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HomGar sensors from a config entry."""
    coordinator: HomgarDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[HomgarSensor] = []
    seen_unique_ids: set[str] = set()
    device_registry = dr.async_get(hass)
    registered_hubs: set[tuple[str, str]] = set()

    for device in coordinator.data.get("devices", []):
        device_sensors: list[HomgarSensor] = []

        if isinstance(device, HomgarHubDevice):
            device_mid = getattr(device, "mid", None)
            mid_str = str(device_mid)
            if mid_str and mid_str.lower() != "unknown":
                hub_identifier = (DOMAIN, mid_str)
                if hub_identifier not in registered_hubs:
                    device_kwargs: dict[str, Any] = {
                        "manufacturer": "RainPoint",
                        "model": getattr(device, "model", None) or device.FRIENDLY_DESC,
                        "name": getattr(device, "name", None) or "RainPoint Hub",
                    }
                    if sw_version := getattr(device, "sw_version", None):
                        device_kwargs["sw_version"] = sw_version
                    if serial := getattr(device, "serial_number", None):
                        device_kwargs["serial_number"] = serial
                    device_registry.async_get_or_create(
                        config_entry_id=config_entry.entry_id,
                        identifiers={hub_identifier},
                        **device_kwargs,
                    )
                    registered_hubs.add(hub_identifier)

        if isinstance(device, RainPointDisplayHub):
            device_sensors = _create_hub_sensors(coordinator, device)
        elif isinstance(device, RainPointGatewayHub):
            device_sensors = _create_gateway_sensors(coordinator, device)
        elif isinstance(device, RainPointSoilMoistureSensor):
            device_sensors = _create_soil_moisture_sensors(coordinator, device)
        elif isinstance(device, RainPointRainSensor):
            device_sensors = _create_rain_sensors(coordinator, device)
        elif isinstance(device, RainPointAirSensor):
            device_sensors = _create_air_sensors(coordinator, device)
        elif isinstance(device, RainPointCO2Sensor):
            device_sensors = _create_co2_sensors(coordinator, device)
        elif isinstance(device, RainPointPoolSensor):
            device_sensors = _create_pool_sensors(coordinator, device)
        else:
            _LOGGER.debug(
                "Unknown device type: %s for device %s",
                type(device).__name__,
                getattr(device, "name", "Unknown"),
            )
            continue

        _LOGGER.debug(
            "Creating %d sensors for device %s (%s)",
            len(device_sensors),
            getattr(device, "name", "Unknown"),
            type(device).__name__,
        )
        for sensor in device_sensors:
            unique_id = sensor.unique_id
            if unique_id is None:
                _LOGGER.debug(
                    "Sensor without unique_id skipped for device %s",
                    getattr(device, "name", "Unknown"),
                )
                continue
            if unique_id in seen_unique_ids:
                _LOGGER.debug(
                    "Skipping duplicate sensor with unique_id %s for device %s",
                    unique_id,
                    getattr(device, "name", "Unknown"),
                )
                continue
            seen_unique_ids.add(unique_id)
            entities.append(sensor)

    async_add_entities(entities)


def _create_hub_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for display hub."""
    sensors: list[HomgarSensor] = []

    # Add common sensors
    add_common_sensors(sensors, coordinator, device, include_humidity=False)

    # Hub-specific sensors
    if description := _get_description("pressure"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointDisplayHub].from_attribute("press_pa_current"),
        )

    create_sensor_if_exists(
        sensors,
        coordinator,
        device,
        create_wifi_rssi_description(),
        SensorSpec[RainPointDisplayHub].from_attribute("wifi_rssi"),
    )

    return sensors


def _create_gateway_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for generic RainPoint gateway hubs."""
    sensors: list[HomgarSensor] = []

    add_common_sensors(sensors, coordinator, device)

    create_sensor_if_exists(
        sensors,
        coordinator,
        device,
        create_wifi_rssi_description(),
        SensorSpec[RainPointGatewayHub].from_attribute("wifi_rssi"),
    )
    if getattr(device, "HAS_BATTERY", True):
        if description := _get_description("battery_state"):
            create_sensor_if_exists(
                sensors,
                coordinator,
                device,
                description,
                SensorSpec[RainPointGatewayHub].from_callable(
                    lambda dev: dev.status_fields.get("battery_state")
                ),
            )

    return sensors


def _create_soil_moisture_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for soil moisture sensor."""
    sensors: list[HomgarSensor] = []

    # Add common sensors
    add_common_sensors(sensors, coordinator, device)

    # Soil moisture specific sensors
    if description := _get_description("soil_moisture"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointSoilMoistureSensor].from_attribute(
                "moist_percent_current"
            ),
        )

    if description := _get_description("light"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointSoilMoistureSensor].from_attribute("light_lux_current"),
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointSoilMoistureSensor].from_attribute("battery_state"),
        )

    return sensors


def _create_rain_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for rain sensor."""
    sensors: list[HomgarSensor] = []

    add_common_sensors(
        sensors,
        coordinator,
        device,
        include_temperature=False,
        include_humidity=False,
    )

    # Rain specific sensors
    if description := _get_description("rainfall_total"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointRainSensor].from_attribute("rainfall_mm_total"),
        )

    if description := _get_description("rainfall_hourly"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointRainSensor].from_attribute("rainfall_mm_hour"),
        )

    if description := _get_description("rainfall_daily"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointRainSensor].from_attribute("rainfall_mm_daily"),
        )

    if description := _get_description("rainfall_weekly"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointRainSensor].from_attribute("rainfall_mm_7days"),
        )

    return sensors


def _create_air_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for air sensor."""
    sensors: list[HomgarSensor] = []

    # Add common sensors
    add_common_sensors(sensors, coordinator, device)
    if description := _get_description("temperature_max"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointAirSensor].from_callable(
                lambda sensor: sensor.temperature_c_max
            ),
        )
    if description := _get_description("temperature_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointAirSensor].from_callable(
                lambda sensor: sensor.temperature_c_min
            ),
        )
    if description := _get_description("humidity_max"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointAirSensor].from_callable(
                lambda sensor: sensor.humidity_pct_max
            ),
        )
    if description := _get_description("humidity_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointAirSensor].from_callable(
                lambda sensor: sensor.humidity_pct_min
            ),
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointAirSensor].from_attribute("battery_state"),
        )

    return sensors


def _create_co2_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for CO₂ sensor."""
    sensors: list[HomgarSensor] = []

    add_common_sensors(sensors, coordinator, device)

    if description := _get_description("co2"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointCO2Sensor].from_callable(
                lambda sensor: sensor.co2_ppm,
                allow_none=False,
            ),
        )
    if description := _get_description("co2_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointCO2Sensor].from_callable(
                lambda sensor: sensor.co2_min_ppm
            ),
        )
    if description := _get_description("co2_max"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointCO2Sensor].from_callable(
                lambda sensor: sensor.co2_max_ppm
            ),
        )
    if description := _get_description("co2_alert"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointCO2Sensor].from_callable(
                lambda sensor: sensor.co2_alert_ppm
            ),
        )

    return sensors


def _create_pool_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: RainPointPoolSensor
) -> list[HomgarSensor]:
    """Create sensors for pool temperature sensor."""
    sensors: list[HomgarSensor] = []

    add_common_sensors(
        sensors,
        coordinator,
        device,
        include_temperature=False,
        include_humidity=False,
    )
    if description := _get_description("pool_water_temp"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointPoolSensor].from_callable(
                lambda sensor: sensor.water_temperature_c
            ),
        )
    if description := _get_description("pool_water_temp_max"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointPoolSensor].from_callable(
                lambda sensor: sensor.water_temperature_c_max
            ),
        )
    if description := _get_description("pool_water_temp_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointPoolSensor].from_callable(
                lambda sensor: sensor.water_temperature_c_min
            ),
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            description,
            SensorSpec[RainPointPoolSensor].from_attribute("battery_state"),
        )

    return sensors


class HomgarSensor(HomgarBaseEntity, SensorEntity):
    """HomGar sensor."""

    def __init__(
        self,
        coordinator: HomgarDataUpdateCoordinator,
        device: Any,
        description: SensorEntityDescription,
        value_fn: Callable[[Any], Any],
    ) -> None:
        """Initialize the sensor."""
        name_suffix = description.name if isinstance(description.name, str) else None
        HomgarBaseEntity.__init__(
            self,
            coordinator,
            device,
            key=description.key,
            name_suffix=name_suffix,
            has_entity_name=name_suffix is None,
        )
        SensorEntity.__init__(self)
        self.entity_description = description
        self._value_fn = value_fn

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        self._refresh_device_reference()
        runtime_device = self._resolve_runtime_device()
        if runtime_device is None:
            unique_id = self.unique_id or self._attr_unique_id or "unknown"
            _log_sensor_debug(unique_id, "device not found")
            return None

        try:
            value = self._value_fn(runtime_device)
        except (AttributeError, TypeError, ValueError) as err:
            unique_id = self.unique_id or self._attr_unique_id or "unknown"
            _log_sensor_debug(unique_id, "error getting value: %s", err)
            return None
        unique_id = self.unique_id or self._attr_unique_id or "unknown"
        _log_sensor_debug(unique_id, "value=%s", value)
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        return self.native_value is not None
