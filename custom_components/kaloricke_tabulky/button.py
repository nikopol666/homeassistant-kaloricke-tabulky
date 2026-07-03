"""Button platform for Kaloricke Tabulky quick food records."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import KalorickeTabulkyError
from .const import CONF_QUICK_FOODS, DOMAIN
from .coordinator import KalorickeTabulkyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kaloricke Tabulky quick food buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        QuickFoodButton(entry, coordinator, preset)
        for preset in entry.options.get(CONF_QUICK_FOODS, [])
        if isinstance(preset, dict) and preset.get("id")
    )


class QuickFoodButton(CoordinatorEntity[KalorickeTabulkyCoordinator], ButtonEntity):
    """Button that records one configured food preset."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: KalorickeTabulkyCoordinator,
        preset: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._preset = preset
        self._attr_unique_id = f"{entry.entry_id}_quick_food_{preset['id']}"
        self._attr_name = _preset_name(preset)
        image_url = _preset_image_url(preset)
        if image_url is not None:
            self._attr_entity_picture = image_url

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Kaloricke Tabulky",
            name=self._entry.title,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return configured food details for dashboard cards."""
        kind = self._preset.get("kind", "food")
        image_url = _preset_image_url(self._preset)
        return {
            "food_guid": self._preset.get("food_guid"),
            "title": self._preset.get("title"),
            "amount": self._preset.get("amount"),
            "unit": self._preset.get("unit"),
            "unit_guid": self._preset.get("unit_guid"),
            "kind": kind,
            "category": self._preset.get("category"),
            "item_class": self._preset.get("item_class"),
            "item_type": "drink" if kind == "drink" else "food",
            "is_drink": kind == "drink",
            "meal_type": self._preset.get("meal_type") or "auto",
            "image_url": image_url,
            "has_image": bool(image_url),
            "image_class": self._preset.get("image_class") or "foodstuff",
        }

    async def async_press(self) -> None:
        """Record the preset food using the current Home Assistant time."""
        now = dt_util.now()
        try:
            await self.coordinator.api.async_record_food(
                food_guid=self._preset["food_guid"],
                kind=self._preset.get("kind", "food"),
                amount=self._preset.get("amount"),
                unit=self._preset.get("unit"),
                unit_guid=self._preset.get("unit_guid"),
                item_class=self._preset.get("item_class"),
                target_date=now.date(),
                target_time=now.strftime("%H:%M"),
                meal_type=self._preset.get("meal_type") or None,
            )
        except KalorickeTabulkyError as err:
            raise HomeAssistantError(str(err)) from err

        await self.coordinator.async_request_refresh()


def _preset_name(preset: dict[str, Any]) -> str:
    title = str(preset.get("title") or "Quick food")
    amount = preset.get("amount")
    unit = preset.get("unit")
    if amount is None:
        return title
    amount_text = f"{amount:g}" if isinstance(amount, float) else str(amount)
    if unit:
        return f"{title} {amount_text} {unit}"
    return f"{title} {amount_text}"


def _preset_image_url(preset: dict[str, Any]) -> str | None:
    image_url = preset.get("image_url")
    if isinstance(image_url, str) and image_url:
        return image_url

    if preset.get("has_image") is False:
        return None

    food_guid = preset.get("food_guid")
    if not food_guid:
        return None
    image_class = preset.get("image_class") or "foodstuff"
    return urljoin(
        "https://www.kaloricketabulky.cz/",
        f"/file/image/thumb/{image_class}/{food_guid}",
    )
