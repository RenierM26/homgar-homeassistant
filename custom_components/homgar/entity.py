"""Shared Home Assistant entity helpers for the HomGar integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .homgarapi.devices import HomgarHubDevice


class HomgarBaseEntity(CoordinatorEntity):
    """Base entity for HomGar platforms."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        device: Any,
        *,
        key: str | None = None,
        name_suffix: str | None = None,
        has_entity_name: bool = False,
    ) -> None:
        """Initialise the entity with device details."""
        super().__init__(coordinator)
        self._device = device
        self._device_mid = self._stringify_identifier(getattr(device, "mid", "unknown"))
        self._device_did = self._stringify_identifier(getattr(device, "did", "unknown"))
        base_name = getattr(device, "name", "Unknown Device")

        if key:
            self._attr_unique_id = f"{self._device_mid}_{self._device_did}_{key}"
        else:
            self._attr_unique_id = f"{self._device_mid}_{self._device_did}"

        if name_suffix:
            self._attr_name = f"{base_name} {name_suffix}"
        elif has_entity_name:
            self._attr_has_entity_name = True
        else:
            self._attr_name = base_name

    @staticmethod
    def _stringify_identifier(value: Any) -> str:
        if value in (None, ""):
            return "unknown"
        return str(value)

    @property
    def device(self) -> Any:
        """Return the device definition used for this entity."""
        return self._device

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self._refresh_device_reference()

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information for the registry."""
        device_name = getattr(self._device, "name", "Unknown Device")
        device_model = getattr(self._device, "model", None)
        device_sw_version = getattr(self._device, "sw_version", None)
        device_serial = getattr(self._device, "serial_number", None)
        device_soft_version = getattr(self._device, "soft_version", None)
        device_mac = getattr(self._device, "mac", None)

        if isinstance(self._device, HomgarHubDevice):
            device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, str(self._device_mid))},
                name=device_name,
                manufacturer="RainPoint",
                model=device_model
                or getattr(self._device, "FRIENDLY_DESC", "Hub"),
            )
        else:
            via_device: tuple[str, str] | None = None
            if self._device_mid != "unknown":
                via_device = (DOMAIN, str(self._device_mid))
            device_info = dr.DeviceInfo(
                identifiers={(DOMAIN, f"{self._device_mid}_{self._device_did}")},
                name=device_name,
                manufacturer="RainPoint",
                model=device_model or "Sensor",
            )
            if via_device is not None:
                device_info["via_device"] = via_device

        if device_sw_version:
            device_info["sw_version"] = device_sw_version
        elif device_soft_version:
            device_info["sw_version"] = device_soft_version
        if device_serial:
            device_info["serial_number"] = device_serial
        if device_mac and device_mac != "00:00:00:00:00:00":
            connections = set(device_info.get("connections", set()))
            connections.add(("mac", device_mac))
            device_info["connections"] = connections

        return device_info

    def _resolve_runtime_device(self) -> Any | None:
        """Return the latest coordinator copy of the device."""
        for device in self.coordinator.data.get("devices", []):
            if (
                self._stringify_identifier(getattr(device, "mid", None))
                == self._device_mid
                and self._stringify_identifier(getattr(device, "did", None))
                == self._device_did
            ):
                return device
        return None

    def _refresh_device_reference(self) -> None:
        """Update cached device reference from coordinator data."""
        if latest := self._resolve_runtime_device():
            self._device = latest

    def _device_is_online(self) -> bool:
        """Return true when the device reports as online."""
        device = self._resolve_runtime_device() or self._device
        if hasattr(device, "online"):
            return bool(getattr(device, "online", True))
        return True

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if not self.coordinator.last_update_success:
            return False
        return self._device_is_online()
