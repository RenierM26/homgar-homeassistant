"""Config flow for HomGar integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow as HAConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError

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

# Constants
DEFAULT_AREA_CODE = "31"
MAX_AREA_CODE_LENGTH = 3
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("area_code", default=DEFAULT_AREA_CODE): str,
    }
)


class ConfigFlow(HAConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomGar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate input format first
            validation_errors = self._validate_input_format(user_input)
            if validation_errors:
                errors.update(validation_errors)
            else:
                # Check for existing entries with same email
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()

                try:
                    result = await self._validate_api_connection(user_input)
                except LoginFailed:
                    errors["base"] = "login_failed"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except InvalidAreaCode:
                    errors["area_code"] = "invalid_area_code"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during setup")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=result["title"],
                        data=result["data"],
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the reauthentication step."""
        entry_id = self.context.get("entry_id")
        if entry_id:
            self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reauth_entry is not None:
            await self.async_set_unique_id(
                self._reauth_entry.data[CONF_EMAIL].lower(),
                raise_on_progress=False,
            )
        if self._reauth_entry is None:
            _LOGGER.error("Reauth requested but no entry found")
            return self.async_abort(reason="reauth_failed")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm updated credentials during reauth."""
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}
        stored_data = self._reauth_entry.data
        default_area = stored_data.get("area_code", DEFAULT_AREA_CODE)

        if user_input is not None:
            merged_input = {
                CONF_EMAIL: stored_data[CONF_EMAIL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                "area_code": user_input.get("area_code", default_area),
            }

            format_errors = self._validate_input_format(merged_input)
            if format_errors:
                errors.update(format_errors)
            else:
                try:
                    result = await self._validate_api_connection(merged_input)
                except LoginFailed:
                    errors["base"] = "login_failed"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except InvalidAreaCode:
                    errors["area_code"] = "invalid_area_code"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during reauth")
                    errors["base"] = "unknown"
                else:
                    new_data = {
                        CONF_EMAIL: result["data"][CONF_EMAIL],
                        CONF_PASSWORD: result["data"][CONF_PASSWORD],
                        "area_code": result["data"]["area_code"],
                    }
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=new_data,
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

        reauth_schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD): str,
                vol.Optional("area_code", default=default_area): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
            description_placeholders={
                "email": stored_data[CONF_EMAIL],
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return HomgarOptionsFlowHandler(config_entry)

    def _validate_input_format(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate input format before attempting API connection."""
        errors: dict[str, str] = {}

        # Validate email format
        email = data.get(CONF_EMAIL, "").strip()
        if not email:
            errors[CONF_EMAIL] = "email_required"
        elif not EMAIL_REGEX.match(email):
            errors[CONF_EMAIL] = "invalid_email"

        # Validate password
        password = data.get(CONF_PASSWORD, "")
        if not password:
            errors[CONF_PASSWORD] = "password_required"
        elif len(password) < 3:  # Basic length check
            errors[CONF_PASSWORD] = "password_too_short"

        # Validate area code
        area_code = data.get("area_code", "").strip()
        if area_code:
            if not area_code.isdigit():
                errors["area_code"] = "area_code_not_numeric"
            elif len(area_code) > MAX_AREA_CODE_LENGTH:
                errors["area_code"] = "area_code_too_long"
            elif len(area_code) == 0:
                errors["area_code"] = "area_code_empty"

        return errors

    async def _validate_api_connection(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate the user input allows us to connect to the API."""
        area_code_raw = data.get("area_code", DEFAULT_AREA_CODE)
        clean_area_code = area_code_raw.strip() or DEFAULT_AREA_CODE
        clean_data = {
            CONF_EMAIL: data[CONF_EMAIL].strip().lower(),
            CONF_PASSWORD: data[CONF_PASSWORD],
            "area_code": clean_area_code,
        }

        api_client = HomgarApiClient(
            email=clean_data[CONF_EMAIL],
            password=clean_data[CONF_PASSWORD],
            area_code=clean_data["area_code"],
        )

        try:
            await self.hass.async_add_executor_job(api_client.ensure_logged_in)
            homes = await self.hass.async_add_executor_job(api_client.get_homes)
        except HomgarApiException as err:
            error_code = getattr(err, "code", None)
            error_message_raw = getattr(err, "message", "") or str(err)
            error_message = error_message_raw.lower()
            if error_code == "invalid_auth":
                raise InvalidAuth from err
            if error_code == "login_failed":
                raise LoginFailed from err
            if any(keyword in error_message for keyword in ("area", "zone", "region")):
                raise InvalidAreaCode from err
            raise CannotConnect from err
        except Exception as err:
            raise CannotConnect from err

        if not homes:
            raise InvalidAreaCode("No homes found for this area code")

        return {
            "title": f"HomGar ({clean_data[CONF_EMAIL]})",
            "data": clean_data,
        }


class HomgarOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle HomGar options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the HomGar options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=current_interval,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=SCAN_INTERVAL_MINUTES_MIN,
                        max=SCAN_INTERVAL_MINUTES_MAX,
                    ),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidAreaCode(HomeAssistantError):
    """Error to indicate invalid area code."""


class LoginFailed(HomeAssistantError):
    """Error to indicate the HomGar API rejected login for non-auth reasons."""
