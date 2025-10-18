"""Sensor platform for HomGar integration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import logging
from typing import Any, Final, Generic, TypeVar, cast

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
from .entity import HomgarBaseEntity, _ensure_hub_registered
from .homgarapi.devices import (
    HomgarDevice,
    RainPointAirSensor,
    RainPointCO2Sensor,
    RainPointDisplayHub,
    RainPointGatewayHub,
    RainPointPoolSensor,
    RainPointRainSensor,
    RainPointSoilMoistureSensor,
)

_LOGGER = logging.getLogger(__name__)
DeviceT = TypeVar("DeviceT")


def _log_sensor_debug(unique_id: str, message: str, *args: Any) -> None:
    """Log a sensor-scoped debug message."""
    if _LOGGER.isEnabledFor(logging.DEBUG):
        formatted = message % args if args else message
        _LOGGER.debug("Sensor %s: %s", unique_id, formatted)


@dataclass(frozen=True)
class SensorSpec(Generic[DeviceT]):
    """Configuration describing how to obtain a sensor value."""

    description_key: str
    value_fn: Callable[[DeviceT], Any]
    allow_none: bool = True


SENSOR_DESCRIPTIONS: Final[dict[str, SensorEntityDescription]] = {
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
    "rf_rssi": SensorEntityDescription(
        key="rf_rssi",
        translation_key="rf_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wifi_rssi": SensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
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


def get_sensor_description(key: str) -> SensorEntityDescription | None:
    """Safely fetch a sensor description by key."""
    if description := SENSOR_DESCRIPTIONS.get(key):
        return description
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
        "pool_water_temperature": SensorEntityDescription(
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
        return description
    _LOGGER.warning("Missing sensor description for key '%s'", key)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HomGar sensors from a config entry."""

    coordinator: HomgarDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    factory = SensorFactory(coordinator)

    entities: list[HomgarSensor] = []
    seen_unique_ids: set[str] = set()
    device_registry = dr.async_get(hass)
    registered_hubs: set[tuple[str, str]] = set()

    for device in coordinator.data.get("devices", []):
        _ensure_hub_registered(device_registry, registered_hubs, config_entry, device)

        for sensor in factory.build(device):
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


class HomgarSensor(HomgarBaseEntity, SensorEntity):
    """HomGar sensor entity."""

    def __init__(
        self,
        coordinator: HomgarDataUpdateCoordinator,
        device: Any,
        description: SensorEntityDescription,
        value_fn: Callable[[Any], Any],
    ) -> None:
        """Initialise the sensor entity."""
        name_suffix = description.name if isinstance(description.name, str) else None
        super().__init__(
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
        """Return availability for the entity."""
        if not super().available:
            return False
        return self.native_value is not None


class SensorFactory:
    """Builder for HomGar sensor entities."""

    def __init__(self, coordinator: HomgarDataUpdateCoordinator) -> None:
        """Initialise the sensor factory."""
        self._coordinator = coordinator

    def build(self, device: HomgarDevice) -> list[HomgarSensor]:
        """Return all sensors applicable to the provided device."""
        if isinstance(device, RainPointDisplayHub):
            sensors = self._build_display_hub(device)
        elif isinstance(device, RainPointGatewayHub):
            sensors = self._build_gateway(device)
        elif isinstance(device, RainPointSoilMoistureSensor):
            sensors = self._build_soil(device)
        elif isinstance(device, RainPointRainSensor):
            sensors = self._build_rain(device)
        elif isinstance(device, RainPointAirSensor):
            sensors = self._build_air(device)
        elif isinstance(device, RainPointCO2Sensor):
            sensors = self._build_co2(device)
        elif isinstance(device, RainPointPoolSensor):
            sensors = self._build_pool(device)
        else:
            _LOGGER.debug(
                "Unknown device type: %s for device %s",
                type(device).__name__,
                getattr(device, "name", "Unknown"),
            )
            return []

        _LOGGER.debug(
            "Creating %d sensors for device %s (%s)",
            len(sensors),
            getattr(device, "name", "Unknown"),
            type(device).__name__,
        )
        return sensors

    def _build_display_hub(self, device: RainPointDisplayHub) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(
            sensors, device, include_temperature=False, include_humidity=False
        )
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointDisplayHub](
                    "pressure", lambda dev: getattr(dev, "press_pa_current", None)
                ),
                SensorSpec[RainPointDisplayHub](
                    "wifi_rssi",
                    lambda dev: getattr(dev, "wifi_rssi", None),
                    allow_none=False,
                ),
            ),
        )
        return sensors

    def _build_gateway(self, device: RainPointGatewayHub) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(
            sensors, device, include_temperature=False, include_humidity=False
        )
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointGatewayHub](
                    "wifi_rssi",
                    lambda dev: getattr(dev, "wifi_rssi", None),
                    allow_none=False,
                ),
                SensorSpec[RainPointGatewayHub](
                    "battery_state",
                    lambda dev: dev.status_fields.get("battery_state")
                    if getattr(dev, "status_fields", None)
                    else None,
                    allow_none=False,
                ),
            ),
        )
        return sensors

    def _build_soil(self, device: RainPointSoilMoistureSensor) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(sensors, device)
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointSoilMoistureSensor](
                    "soil_moisture",
                    lambda dev: getattr(dev, "moist_percent_current", None),
                ),
                SensorSpec[RainPointSoilMoistureSensor](
                    "light", lambda dev: getattr(dev, "light_lux_current", None)
                ),
                SensorSpec[RainPointSoilMoistureSensor](
                    "battery_state", lambda dev: getattr(dev, "battery_state", None)
                ),
            ),
        )
        return sensors

    def _build_rain(self, device: RainPointRainSensor) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(
            sensors, device, include_temperature=False, include_humidity=False
        )
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointRainSensor](
                    "rainfall_total",
                    lambda dev: getattr(dev, "rainfall_mm_total", None),
                ),
                SensorSpec[RainPointRainSensor](
                    "rainfall_hourly",
                    lambda dev: getattr(dev, "rainfall_mm_hour", None),
                ),
                SensorSpec[RainPointRainSensor](
                    "rainfall_daily",
                    lambda dev: getattr(dev, "rainfall_mm_daily", None),
                ),
                SensorSpec[RainPointRainSensor](
                    "rainfall_weekly",
                    lambda dev: getattr(dev, "rainfall_mm_7days", None),
                ),
            ),
        )
        return sensors

    def _build_air(self, device: RainPointAirSensor) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(sensors, device)
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointAirSensor](
                    "temperature_max", lambda dev: dev.temperature_c_max
                ),
                SensorSpec[RainPointAirSensor](
                    "temperature_min", lambda dev: dev.temperature_c_min
                ),
                SensorSpec[RainPointAirSensor](
                    "humidity_max", lambda dev: dev.humidity_pct_max
                ),
                SensorSpec[RainPointAirSensor](
                    "humidity_min", lambda dev: dev.humidity_pct_min
                ),
                SensorSpec[RainPointAirSensor](
                    "battery_state", lambda dev: dev.battery_state
                ),
            ),
        )
        return sensors

    def _build_co2(self, device: RainPointCO2Sensor) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(sensors, device)
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointCO2Sensor](
                    "co2", lambda dev: dev.co2_ppm, allow_none=False
                ),
                SensorSpec[RainPointCO2Sensor]("co2_min", lambda dev: dev.co2_min_ppm),
                SensorSpec[RainPointCO2Sensor]("co2_max", lambda dev: dev.co2_max_ppm),
                SensorSpec[RainPointCO2Sensor](
                    "co2_alert", lambda dev: dev.co2_alert_ppm
                ),
            ),
        )
        return sensors

    def _build_pool(self, device: RainPointPoolSensor) -> list[HomgarSensor]:
        sensors: list[HomgarSensor] = []
        self._add_common_sensors(
            sensors, device, include_temperature=False, include_humidity=False
        )
        self._add_from_specs(
            sensors,
            device,
            (
                SensorSpec[RainPointPoolSensor](
                    "pool_water_temp", lambda dev: dev.water_temperature_c
                ),
                SensorSpec[RainPointPoolSensor](
                    "pool_water_temp_max", lambda dev: dev.water_temperature_c_max
                ),
                SensorSpec[RainPointPoolSensor](
                    "pool_water_temp_min", lambda dev: dev.water_temperature_c_min
                ),
                SensorSpec[RainPointPoolSensor](
                    "battery_state", lambda dev: dev.battery_state
                ),
            ),
        )
        return sensors

    def _add_common_sensors(
        self,
        sensors: list[HomgarSensor],
        device: HomgarDevice,
        *,
        include_temperature: bool = True,
        include_humidity: bool = True,
    ) -> None:
        specs: list[SensorSpec[HomgarDevice]] = []

        rf_rssi = getattr(device, "rf_rssi", None)
        if rf_rssi is not None:
            specs.append(
                SensorSpec[HomgarDevice](
                    "rf_rssi",
                    lambda dev: getattr(dev, "rf_rssi", None),
                    allow_none=False,
                )
            )

        if include_temperature:
            temperature = getattr(device, "temperature_c", None)
            if temperature is not None:
                specs.append(
                    SensorSpec[HomgarDevice](
                        "temperature",
                        lambda dev: cast(
                            float | None, getattr(dev, "temperature_c", None)
                        ),
                    )
                )
        if include_humidity:
            humidity = getattr(device, "humidity_pct", None)
            if humidity is not None:
                specs.append(
                    SensorSpec[HomgarDevice](
                        "humidity",
                        lambda dev: cast(
                            int | None, getattr(dev, "humidity_pct", None)
                        ),
                    )
                )

        if getattr(device, "HAS_BATTERY", True):
            battery_level = getattr(device, "battery_level", None)
            if battery_level is not None:
                specs.append(
                    SensorSpec[HomgarDevice](
                        "battery",
                        lambda dev: getattr(dev, "battery_level", None),
                        allow_none=False,
                    )
                )
            battery_state = getattr(device, "battery_state", None)
            if battery_state is not None:
                specs.append(
                    SensorSpec[HomgarDevice](
                        "battery_state",
                        lambda dev: getattr(dev, "battery_state", None),
                        allow_none=False,
                    )
                )

        if getattr(device, "last_seen", None) is not None:
            specs.append(
                SensorSpec[HomgarDevice](
                    "last_seen",
                    lambda dev: dt_util.parse_datetime(str(dev.last_seen))
                    if getattr(dev, "last_seen", None)
                    else None,
                )
            )

        self._add_from_specs(sensors, device, specs)

    def _add_from_specs(
        self,
        sensors: list[HomgarSensor],
        device: DeviceT,
        specs: Sequence[SensorSpec[DeviceT]],
    ) -> None:
        for spec in specs:
            description = get_sensor_description(spec.description_key)
            if description is None:
                continue
            if not self._supports_sensor(device, description.key):
                continue
            try:
                candidate = spec.value_fn(device)
            except (AttributeError, TypeError, ValueError):
                continue
            if candidate is None and not spec.allow_none:
                continue
            sensors.append(
                HomgarSensor(
                    self._coordinator,
                    device,
                    description,
                    spec.value_fn,
                )
            )

    @staticmethod
    def _supports_sensor(device: DeviceT, sensor_key: str) -> bool:
        supports = getattr(device, "supports_sensor", lambda key: True)
        return supports(sensor_key)


def build_sensors_for_device(
    coordinator: HomgarDataUpdateCoordinator,
    device: HomgarDevice,
) -> list[HomgarSensor]:
    """Convenience wrapper around SensorFactory for simple imports."""
    return SensorFactory(coordinator).build(device)
