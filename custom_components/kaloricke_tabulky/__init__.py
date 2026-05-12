"""The Kaloricke Tabulky integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import KalorickeTabulkyApi, KalorickeTabulkyError, parse_service_date
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DATE,
    ATTR_WEIGHT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SERVICE_RECORD_WEIGHT,
)
from .coordinator import KalorickeTabulkyCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_RECORD_WEIGHT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_WEIGHT): vol.Coerce(float),
        vol.Optional(ATTR_DATE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up integration-level services."""

    async def handle_record_weight(call: ServiceCall) -> None:
        entries = hass.config_entries.async_entries(DOMAIN)
        config_entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)

        if config_entry_id:
            entry = next((item for item in entries if item.entry_id == config_entry_id), None)
            if entry is None:
                raise HomeAssistantError("Unknown Kaloricke Tabulky config entry")
        elif len(entries) == 1:
            entry = entries[0]
        elif not entries:
            raise HomeAssistantError("Set up Kaloricke Tabulky before recording weight")
        else:
            raise HomeAssistantError(
                "Select config_entry_id when more than one Kaloricke Tabulky account is configured"
            )

        coordinator = entry.runtime_data
        try:
            target_date = parse_service_date(call.data.get(ATTR_DATE)) or dt_util.now().date()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        try:
            await coordinator.api.async_record_weight(call.data[ATTR_WEIGHT], target_date)
        except KalorickeTabulkyError as err:
            raise HomeAssistantError(str(err)) from err

        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_WEIGHT,
        handle_record_weight,
        schema=SERVICE_RECORD_WEIGHT_SCHEMA,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Kaloricke Tabulky from a config entry."""
    session = async_get_clientsession(hass)
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
