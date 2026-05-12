"""Data coordinator for the Kaloricke Tabulky integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import KalorickeTabulkyApi, KalorickeTabulkyError, SummaryData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class KalorickeTabulkyCoordinator(DataUpdateCoordinator[SummaryData]):
    """Coordinate polling of Kaloricke Tabulky data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: KalorickeTabulkyApi,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.api = api

    async def _async_update_data(self) -> SummaryData:
        try:
            return await self.api.async_get_summary(dt_util.now().date())
        except KalorickeTabulkyError as err:
            raise UpdateFailed(str(err)) from err
