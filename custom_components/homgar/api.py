"""Thin wrapper around the bundled HomGar API library."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .homgarapi import HomgarApi, HomgarApiException

_LOGGER = logging.getLogger(__name__)

# Constants
REQUEST_TIMEOUT = 30


class HomgarApiClient:
    """Home Assistant friendly wrapper for the HomGar API."""

    def __init__(
        self,
        *,
        email: str,
        password: str,
        area_code: str = "31",
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        """Initialise the client wrapper with account credentials."""
        self.email = email
        self.password = password
        self.area_code = area_code
        self._api = HomgarApi()
        self._timeout = timeout

    def ensure_logged_in(self) -> None:
        """Ensure we're logged into the API with retry logic."""
        try:
            self._api.ensure_logged_in_with_retries(
                self.email,
                self.password,
                self.area_code,
            )
            _LOGGER.debug("Successfully logged in to HomGar API")

        except HomgarApiException as err:
            error_str = str(err).lower()
            if "invalid_auth" in error_str:
                _LOGGER.error(
                    "Authentication failed for HomGar API - check credentials: %s",
                    err,
                )
                _raise_homgar_exception("invalid_auth", "Invalid credentials", err)
            if "connection_timeout" in error_str:
                _LOGGER.error("Connection timeout to HomGar API: %s", err)
                _raise_homgar_exception("connection_timeout", "Connection timeout", err)
            _LOGGER.error(
                "Failed to login to HomGar API: %s",
                err,
            )
            raise

        except Exception as err:  # noqa: BLE001 - bubble unexpected failures with context
            _LOGGER.error("Unexpected error during HomGar API login: %s", err)
            _raise_homgar_exception("login_failed", f"Login failed: {err}", err)

    def get_homes(self) -> list[Any]:
        """Return the list of homes associated with the account."""
        return self._api.get_homes()

    def get_devices_for_hid(self, hid: str) -> list[Any]:
        """Return device tree for the provided home id."""
        return self._api.get_devices_for_hid(hid)

    def get_device_status(self, hub: Any) -> None:
        """Populate status for the provided hub and its subdevices."""
        self._api.get_device_status(hub)

    def is_authenticated(self) -> bool:
        """Check if the underlying library has an active session."""
        session = getattr(self._api, "_session", None)
        return session is not None

    def reset_connection(self) -> None:
        """Reset API connection (useful for error recovery)."""
        self._api = HomgarApi()
        _LOGGER.info("Reset HomGar API connection")

    async def async_health_check(self) -> bool:
        """Check if the API connection is healthy."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._api.health_check)

    @property
    def retry_count(self) -> int:
        """Return current login retry count."""
        manager = getattr(self._api, "_auth_manager", None)
        return manager.retry_count if manager else 0

    @property
    def last_login_time(self) -> float:
        """Return timestamp of the last login attempt."""
        manager = getattr(self._api, "_auth_manager", None)
        return manager.last_attempt if manager else 0.0


def _raise_homgar_exception(
    error_code: Any,
    message: str,
    err: Exception | None = None,
) -> None:
    exception = HomgarApiException(error_code, message)
    if err is not None:
        raise exception from err
    raise exception
