"""The Kaloricke Tabulky integration."""

from __future__ import annotations

from datetime import timedelta
from math import isfinite
from typing import Any

from aiohttp import DummyCookieJar
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import (
    KalorickeTabulkyApi,
    KalorickeTabulkyError,
    parse_service_date,
    parse_service_time,
)
from .const import (
    ATTR_AMOUNT,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DATE,
    ATTR_FOOD_GUID,
    ATTR_KIND,
    ATTR_MEAL_TYPE,
    ATTR_PAGE,
    ATTR_QUERY,
    ATTR_TIME,
    ATTR_UNIT,
    ATTR_UNIT_GUID,
    ATTR_WEIGHT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SERVICE_RECORD_FOOD,
    SERVICE_RECORD_WEIGHT,
    SERVICE_SEARCH_FOOD,
)
from .coordinator import KalorickeTabulkyCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _positive_finite_number(value: float) -> float:
    if not isfinite(value) or value <= 0:
        raise vol.Invalid("Value must be a positive finite number")
    return value

SERVICE_RECORD_WEIGHT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_WEIGHT): vol.Coerce(float),
        vol.Optional(ATTR_DATE): cv.string,
    }
)

SERVICE_SEARCH_FOOD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_KIND, default="food"): vol.In(("food", "drink")),
        vol.Optional(ATTR_PAGE, default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

SERVICE_RECORD_FOOD_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_FOOD_GUID): cv.string,
        vol.Optional(ATTR_KIND, default="food"): vol.In(("food", "drink")),
        vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), _positive_finite_number),
        vol.Optional(ATTR_UNIT): cv.string,
        vol.Optional(ATTR_UNIT_GUID): cv.string,
        vol.Optional(ATTR_DATE): cv.string,
        vol.Optional(ATTR_TIME): cv.string,
        vol.Optional(ATTR_MEAL_TYPE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-level services."""

    async def handle_record_weight(call: ServiceCall) -> None:
        coordinator = _coordinator_from_service_call(hass, call, "recording weight")
        try:
            target_date = parse_service_date(call.data.get(ATTR_DATE)) or dt_util.now().date()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        try:
            await coordinator.api.async_record_weight(call.data[ATTR_WEIGHT], target_date)
        except KalorickeTabulkyError as err:
            raise HomeAssistantError(str(err)) from err

        await coordinator.async_request_refresh()

    async def handle_search_food(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator_from_service_call(hass, call, "searching food")
        try:
            results = await coordinator.api.async_search_food(
                call.data[ATTR_QUERY],
                call.data[ATTR_KIND],
                call.data[ATTR_PAGE],
            )
        except KalorickeTabulkyError as err:
            raise HomeAssistantError(str(err)) from err
        return {"results": results}

    async def handle_record_food(call: ServiceCall) -> ServiceResponse | None:
        if not call.data.get(ATTR_QUERY) and not call.data.get(ATTR_FOOD_GUID):
            raise HomeAssistantError("Set query or food_guid")

        coordinator = _coordinator_from_service_call(hass, call, "recording food")
        try:
            target_date = parse_service_date(call.data.get(ATTR_DATE)) or dt_util.now().date()
            target_time = parse_service_time(call.data.get(ATTR_TIME)) or dt_util.now().strftime(
                "%H:%M"
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        try:
            result = await coordinator.api.async_record_food(
                query=call.data.get(ATTR_QUERY),
                food_guid=call.data.get(ATTR_FOOD_GUID),
                kind=call.data[ATTR_KIND],
                amount=call.data.get(ATTR_AMOUNT),
                unit=call.data.get(ATTR_UNIT),
                unit_guid=call.data.get(ATTR_UNIT_GUID),
                target_date=target_date,
                target_time=target_time,
                meal_type=call.data.get(ATTR_MEAL_TYPE),
            )
        except KalorickeTabulkyError as err:
            raise HomeAssistantError(str(err)) from err

        await coordinator.async_request_refresh()
        return result if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_WEIGHT,
        handle_record_weight,
        schema=SERVICE_RECORD_WEIGHT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_FOOD,
        handle_search_food,
        schema=SERVICE_SEARCH_FOOD_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_FOOD,
        handle_record_food,
        schema=SERVICE_RECORD_FOOD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


def _coordinator_from_service_call(
    hass: HomeAssistant, call: ServiceCall, action: str
) -> KalorickeTabulkyCoordinator:
    entries = hass.config_entries.async_entries(DOMAIN)
    config_entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)

    if config_entry_id:
        entry = next((item for item in entries if item.entry_id == config_entry_id), None)
        if entry is None:
            raise HomeAssistantError("Unknown Kaloricke Tabulky config entry")
    elif len(entries) == 1:
        entry = entries[0]
    elif not entries:
        raise HomeAssistantError(f"Set up Kaloricke Tabulky before {action}")
    else:
        raise HomeAssistantError(
            "Select config_entry_id when more than one Kaloricke Tabulky account is configured"
        )

    if entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(
            f"Kaloricke Tabulky account must be loaded before {action}"
        )

    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        raise HomeAssistantError(
            f"Kaloricke Tabulky account is not ready for {action}"
        )

    return coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Kaloricke Tabulky from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=DummyCookieJar())
    api = KalorickeTabulkyApi(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    interval_minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = KalorickeTabulkyCoordinator(
        hass,
        api,
        timedelta(minutes=max(MIN_SCAN_INTERVAL, interval_minutes)),
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
