"""Sensor platform for HomGar integration."""

from __future__ import annotations

from collections.abc import Callable
import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomgarDataUpdateCoordinator
from .const import DOMAIN
from .homgarapi.devices import (
    HomgarHubDevice,
    RainPointAirSensor,
    RainPointDisplayHub,
    RainPointGatewayHub,
    RainPointPoolSensor,
    RainPointRainSensor,
    RainPointSoilMoistureSensor,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "temperature_max": SensorEntityDescription(
        key="temperature_max",
        name="Temperature Max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "temperature_min": SensorEntityDescription(
        key="temperature_min",
        name="Temperature Min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "humidity_max": SensorEntityDescription(
        key="humidity_max",
        name="Humidity Max",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "humidity_min": SensorEntityDescription(
        key="humidity_min",
        name="Humidity Min",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
    ),
    "soil_moisture": SensorEntityDescription(
        key="soil_moisture",
        name="Soil Moisture",
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "light": SensorEntityDescription(
        key="light",
        name="Light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    "rainfall_total": SensorEntityDescription(
        key="rainfall_total",
        name="Total Rainfall",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    "rainfall_hourly": SensorEntityDescription(
        key="rainfall_hourly",
        name="Hourly Rainfall",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mm/h",
    ),
    "rainfall_daily": SensorEntityDescription(
        key="rainfall_daily",
        name="Daily Rainfall",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    "rainfall_weekly": SensorEntityDescription(
        key="rainfall_weekly",
        name="7-Day Rainfall",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
    ),
    "rssi": SensorEntityDescription(
        key="rssi",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery_state": SensorEntityDescription(
        key="battery_state",
        name="Battery State",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "pool_water_temp": SensorEntityDescription(
        key="pool_water_temperature",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "pool_water_temp_max": SensorEntityDescription(
        key="pool_water_temperature_max",
        name="Water Temperature Max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "pool_water_temp_min": SensorEntityDescription(
        key="pool_water_temperature_min",
        name="Water Temperature Min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "last_seen": SensorEntityDescription(
        key="last_seen",
        name="Last Data Received",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
}


def create_rf_rssi_description() -> SensorEntityDescription:
    """Create RF RSSI sensor description."""
    return SensorEntityDescription(
        key="rf_rssi",
        name="RF Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
    )


def create_wifi_rssi_description() -> SensorEntityDescription:
    """Create WiFi RSSI sensor description."""
    return SensorEntityDescription(
        key="wifi_rssi",
        name="WiFi Signal Strength",
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
                name="Humidity",
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
            ),
            "battery": SensorEntityDescription(
                key="battery",
                name="Battery",
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "light": SensorEntityDescription(
                key="light",
                name="Light",
                device_class=SensorDeviceClass.ILLUMINANCE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=LIGHT_LUX,
            ),
            "battery_state": SensorEntityDescription(
                key="battery_state",
                name="Battery State",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "pool_water_temp": SensorEntityDescription(
                key="pool_water_temperature",
                name="Water Temperature",
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


def create_sensor_if_exists(
    sensors: list[HomgarSensor],
    coordinator: HomgarDataUpdateCoordinator,
    device: Any,
    attr_name: str,
    description: SensorEntityDescription,
    value_fn: Callable[[Any], Any] | None = None,
    *,
    allow_none: bool = True,
    requires_attribute: bool = True,
) -> None:
    """Helper to create sensor if attribute exists on device."""
    if not requires_attribute and value_fn is None:
        raise ValueError("value_fn must be provided when requires_attribute is False")

    supports_sensor = getattr(device, "supports_sensor", lambda key: True)
    if not supports_sensor(description.key):
        return

    if requires_attribute:
        if not hasattr(device, attr_name):
            return
        try:
            attr_value = getattr(device, attr_name)
        except AttributeError:
            return
        if attr_value is None and not allow_none:
            return
    elif not allow_none:
        assert value_fn is not None
        try:
            candidate_value = value_fn(device)
        except (AttributeError, TypeError, ValueError):
            return
        if candidate_value is None:
            return

    final_value_fn = value_fn or _attribute_getter(attr_name)
    sensors.append(
        HomgarSensor(
            coordinator,
            device,
            description,
            final_value_fn,
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
            "temperature",
            description,
            lambda d: getattr(d, "temperature_c", None),
            requires_attribute=False,
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
            "humidity",
            description,
            lambda d: getattr(d, "humidity_pct", None),
            requires_attribute=False,
        )

    # RF RSSI sensor (common pattern)
    create_sensor_if_exists(
        sensors,
        coordinator,
        device,
        "rf_rssi",
        create_rf_rssi_description(),
        allow_none=False,
    )

    # Battery sensor (common pattern)
    if description := _get_description("battery"):
        if getattr(device, "HAS_BATTERY", True):
            create_sensor_if_exists(
                sensors,
                coordinator,
                device,
                "battery_level",
                description,
            )
    if description := _get_description("battery_state"):
        if getattr(device, "HAS_BATTERY", True):
            create_sensor_if_exists(
                sensors,
                coordinator,
                device,
                "battery_state",
                description,
                lambda d: d.battery_state,
            )
    if (description := _get_description("last_seen")) and getattr(device, "last_seen", None):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "last_seen",
            description,
            lambda d: datetime.datetime.fromisoformat(str(d.last_seen)) if d.last_seen else None,
            allow_none=True,
            requires_attribute=False,
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
                        "model": getattr(device, "model", None)
                        or device.FRIENDLY_DESC,
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
            "press_pa_current",
            description,
        )

    create_sensor_if_exists(
        sensors, coordinator, device, "wifi_rssi", create_wifi_rssi_description()
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
        "wifi_rssi",
        create_wifi_rssi_description(),
    )
    if getattr(device, "HAS_BATTERY", True):
        if description := _get_description("battery_state"):
            create_sensor_if_exists(
                sensors,
                coordinator,
                device,
                "status_fields",
                description,
                lambda d: d.status_fields.get("battery_state"),
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
            "moist_percent_current",
            description,
        )

    if description := _get_description("light"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "light_lux_current",
            description,
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "battery_state",
            description,
            lambda d: d.battery_state,
        )

    return sensors


def _create_rain_sensors(
    coordinator: HomgarDataUpdateCoordinator, device: Any
) -> list[HomgarSensor]:
    """Create sensors for rain sensor."""
    sensors: list[HomgarSensor] = []

    # Add common sensors (only RF RSSI and battery for rain sensors)
    create_sensor_if_exists(
        sensors, coordinator, device, "rf_rssi", create_rf_rssi_description()
    )

    if description := _get_description("battery"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "battery_level",
            description,
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "battery_state",
            description,
            lambda d: d.battery_state,
        )

    # Rain specific sensors
    if description := _get_description("rainfall_total"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "rainfall_mm_total",
            description,
        )

    if description := _get_description("rainfall_hourly"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "rainfall_mm_hour",
            description,
        )

    if description := _get_description("rainfall_daily"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "rainfall_mm_daily",
            description,
        )

    if description := _get_description("rainfall_weekly"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "rainfall_mm_7days",
            description,
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
            "temperature_max",
            description,
            lambda d: getattr(d, "temperature_c_max", None),
            requires_attribute=False,
        )
    if description := _get_description("temperature_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "temperature_min",
            description,
            lambda d: getattr(d, "temperature_c_min", None),
            requires_attribute=False,
        )
    if description := _get_description("humidity_max"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "humidity_max",
            description,
            lambda d: getattr(d, "humidity_pct_max", None),
            requires_attribute=False,
        )
    if description := _get_description("humidity_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "humidity_min",
            description,
            lambda d: getattr(d, "humidity_pct_min", None),
            requires_attribute=False,
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "battery_state",
            description,
            lambda d: d.battery_state,
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
            "water_temperature",
            description,
            lambda d: getattr(d, "water_temperature_c", None),
            requires_attribute=False,
        )
    if description := _get_description("pool_water_temp_max"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "water_temperature_max",
            description,
            lambda d: getattr(d, "water_temperature_c_max", None),
            requires_attribute=False,
        )
    if description := _get_description("pool_water_temp_min"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "water_temperature_min",
            description,
            lambda d: getattr(d, "water_temperature_c_min", None),
            requires_attribute=False,
        )
    if description := _get_description("battery_state"):
        create_sensor_if_exists(
            sensors,
            coordinator,
            device,
            "battery_state",
            description,
            lambda d: d.battery_state,
        )

    return sensors


class HomgarSensor(CoordinatorEntity, SensorEntity):
    """HomGar sensor."""

    def __init__(
        self,
        coordinator: HomgarDataUpdateCoordinator,
        device: Any,
        description: SensorEntityDescription,
        value_fn: Callable[[Any], Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        self._value_fn = value_fn

        # Safely get device identifiers with fallbacks
        device_mid = getattr(device, "mid", "unknown")
        device_did = getattr(device, "did", "unknown")
        device_name = getattr(device, "name", "Unknown Device")

        self._attr_unique_id = f"{device_mid}_{device_did}_{description.key}"
        self._attr_name = f"{device_name} {description.name}"

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        device_mid = getattr(self._device, "mid", "unknown")
        device_did = getattr(self._device, "did", "unknown")
        device_name = getattr(self._device, "name", "Unknown Device")
        device_model = getattr(self._device, "model", None)
        device_sw_version = getattr(self._device, "sw_version", None)
        device_serial = getattr(self._device, "serial_number", None)

        # For hub devices (main devices)
        if isinstance(self._device, HomgarHubDevice):
            device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, str(device_mid))},
                name=device_name,
                manufacturer="RainPoint",
                model=device_model or getattr(
                    self._device, "FRIENDLY_DESC", "Hub"
                ),
            )
        # For sub-devices that connect through a hub
        else:
            via_device: tuple[str, str] | None = None
            if device_mid not in ("unknown", None):
                via_device = (DOMAIN, str(device_mid))
            device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, f"{device_mid}_{device_did}")},
                name=device_name,
                manufacturer="RainPoint",
                model=device_model or "Sensor",
            )
            if via_device is not None:
                device_info["via_device"] = via_device

        # Add optional fields if available
        if device_sw_version:
            device_info["sw_version"] = device_sw_version
        if device_serial:
            device_info["serial_number"] = device_serial

        return device_info

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        device_mid = getattr(self._device, "mid", None)
        device_did = getattr(self._device, "did", None)

        if device_mid is None or device_did is None:
            _LOGGER.warning("Device missing mid or did: %s", self._attr_unique_id)
            return None

        for device in self.coordinator.data.get("devices", []):
            if (
                getattr(device, "mid", None) == device_mid
                and getattr(device, "did", None) == device_did
            ):
                try:
                    value = self._value_fn(device)
                except (AttributeError, TypeError, ValueError) as err:
                    _LOGGER.debug(
                        "Error getting value for %s: %s", self._attr_unique_id, err
                    )
                    return None
                _LOGGER.debug("Got value %s for sensor %s", value, self._attr_unique_id)
                return value

        _LOGGER.debug("Device not found for sensor %s", self._attr_unique_id)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        # Check if device is online if that information is available
        if hasattr(self._device, "online"):
            return getattr(self._device, "online", True)

        # Check if we have a valid value
        return self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        attributes: dict[str, Any] = {}

        # Add device online status if available
        if hasattr(self._device, "online"):
            attributes["device_online"] = getattr(self._device, "online", False)

        # Add last seen timestamp if available
        if hasattr(self._device, "last_seen"):
            last_seen = getattr(self._device, "last_seen", None)
            if last_seen:
                attributes["last_seen"] = last_seen

        # Add signal quality indicators
        if hasattr(self._device, "rf_rssi"):
            rf_rssi = getattr(self._device, "rf_rssi", None)
            if rf_rssi is not None:
                attributes["rf_signal_quality"] = (
                    "Excellent"
                    if rf_rssi > -50
                    else "Good"
                    if rf_rssi > -70
                    else "Fair"
                    if rf_rssi > -85
                    else "Poor"
                )

        if hasattr(self._device, "wifi_rssi"):
            wifi_rssi = getattr(self._device, "wifi_rssi", None)
            if wifi_rssi is not None:
                attributes["wifi_signal_quality"] = (
                    "Excellent"
                    if wifi_rssi > -50
                    else "Good"
                    if wifi_rssi > -70
                    else "Fair"
                    if wifi_rssi > -85
                    else "Poor"
                )

        return attributes if attributes else None
