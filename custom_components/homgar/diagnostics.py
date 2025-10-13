"""Diagnostics support for HomGar."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from . import HomgarDataUpdateCoordinator
from .const import DOMAIN

IGNORED_ATTRS = {"password", "email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HomgarDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get device info without sensitive data
    devices_info: list[dict[str, Any]] = []
    for device in coordinator.data.get("devices", []):
        device_dict: dict[str, Any] = {}
        device_info = {
            "name": getattr(device, "name", "Unknown"),
            "model": getattr(device, "model", "Unknown"),
            "mid": getattr(device, "mid", "Unknown"),
            "did": getattr(device, "did", "Unknown"),
            "type": type(device).__name__,
            "online": getattr(device, "online", False),
        }

        # Gather raw attributes for debugging, filtering private/sensitive ones
        for attr_name in dir(device):
            if attr_name.startswith("_") or attr_name in device_info or attr_name in IGNORED_ATTRS:
                continue
            if attr_name in ("set_device_status", "get_device_status_ids", "_parse_status_d_value"):
                continue
            value = getattr(device, attr_name, None)
            if callable(value):
                continue
            if value is None:
                continue
            if isinstance(value, (int, float, str, bool)):
                device_dict[attr_name] = value
            elif isinstance(value, (list, tuple)):
                device_dict[attr_name] = list(value)
            elif isinstance(value, dict):
                device_dict[attr_name] = value

        # Add sensor values (non-sensitive)
        if hasattr(device, "temp_mk_current") and device.temp_mk_current is not None:
            device_info["temperature"] = round((device.temp_mk_current * 1e-3 - 273.15), 2)
        if hasattr(device, "hum_current") and device.hum_current is not None:
            device_info["humidity"] = device.hum_current
        if hasattr(device, "moist_percent_current") and device.moist_percent_current is not None:
            device_info["soil_moisture"] = device.moist_percent_current
        if hasattr(device, "rainfall_mm_total") and device.rainfall_mm_total is not None:
            device_info["rainfall_total"] = device.rainfall_mm_total
        if hasattr(device, "rf_rssi") and device.rf_rssi is not None:
            device_info["rf_rssi"] = device.rf_rssi
        if hasattr(device, "wifi_rssi") and device.wifi_rssi is not None:
            device_info["wifi_rssi"] = device.wifi_rssi
        for attr_name, key in (
            ("water_temp_c", "water_temp_c"),
            ("water_temp_f", "water_temp_f"),
            ("battery_state", "battery_state"),
            ("battery_level", "battery_level"),
            ("battery_level_raw", "battery_level_raw"),
            ("moist_percent_current", "soil_moisture"),
            ("light_lux_current", "illuminance_lux"),
            ("signal_strength", "signal_strength"),
        ):
            if hasattr(device, attr_name):
                value = getattr(device, attr_name)
                if value is not None:
                    device_info[key] = value

        if device_dict:
            device_info["raw_attributes"] = device_dict

        if hasattr(device, "last_status_payload"):
            device_info["last_status_payload"] = device.last_status_payload
        if hasattr(device, "status_fields") and device.status_fields:
            raw_attrs = cast(dict[str, Any], device_info.setdefault("raw_attributes", {}))
            raw_attrs["status_fields"] = device.status_fields

        devices_info.append(device_info)

    integration = await async_get_integration(hass, DOMAIN)

    diagnostics: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
            "homes_count": len(coordinator.data.get("homes", [])),
            "devices_count": len(coordinator.data.get("devices", [])),
        },
        "devices": devices_info,
        "integration_manifest": integration.manifest,
    }

    if coordinator.homes:
        diagnostics["homes"] = [
            {
                "hid": getattr(home, "hid", "Unknown"),
                "name": getattr(home, "name", "Unknown"),
                "raw": {
                    key: value
                    for key, value in vars(home).items()
                    if not key.startswith("_") and value is not None
                },
            }
            for home in coordinator.homes
        ]

    return diagnostics
