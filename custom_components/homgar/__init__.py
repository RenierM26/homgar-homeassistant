"""HomGar integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HomgarApiClient
from .const import (
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    SCAN_INTERVAL_MINUTES_MAX,
    SCAN_INTERVAL_MINUTES_MIN,
)
from .homgarapi import HomgarApiException

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomGar from a config entry."""
    coordinator = HomgarDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HomgarDataUpdateCoordinator(DataUpdateCoordinator[dict[str, list[Any]]]):
    """Class to manage fetching data from the HomGar API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.api = HomgarApiClient(
            email=entry.data["email"],
            password=entry.data["password"],
            area_code=entry.data.get("area_code", "31"),
        )
        self.homes: list[Any] = []
        self.devices: list[Any] = []
        scan_interval = _determine_scan_interval(entry)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )

    async def _async_update_data(self) -> dict[str, list[Any]]:
        """Update data via library."""
        try:
            await self.hass.async_add_executor_job(self._update_data)
        except HomgarApiException as exception:
            _LOGGER.error("Error communicating with HomGar API: %s", exception)
            raise UpdateFailed(
                f"Error communicating with API: {exception}"
            ) from exception
        except Exception as exception:
            _LOGGER.error("Unexpected error updating HomGar data: %s", exception)
            raise UpdateFailed(f"Unexpected error: {exception}") from exception

        return {"homes": self.homes, "devices": self.devices}

    def _update_data(self) -> None:
        """Fetch data from API endpoint."""
        self.api.ensure_logged_in()
        self.homes = self.api.get_homes()
        self.devices = []

        _LOGGER.debug("Found %d homes", len(self.homes))

        for home in self.homes:
            hubs = self.api.get_devices_for_hid(home.hid)
            for hub in hubs:
                self.api.get_device_status(hub)
                self.devices.append(hub)
                self.devices.extend(hub.subdevices)

        _LOGGER.debug("Total devices discovered: %d", len(self.devices))


def _determine_scan_interval(entry: ConfigEntry) -> timedelta:
    """Calculate the scan interval for the given entry."""
    raw_value = entry.options.get(
        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
    )
    try:
        minutes = int(raw_value)
    except (TypeError, ValueError):
        minutes = DEFAULT_SCAN_INTERVAL_MINUTES
    minutes = max(SCAN_INTERVAL_MINUTES_MIN, min(minutes, SCAN_INTERVAL_MINUTES_MAX))
    return timedelta(minutes=minutes)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry options update."""
    await hass.config_entries.async_reload(entry.entry_id)
