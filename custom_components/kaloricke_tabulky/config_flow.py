"""Config flow for the Kaloricke Tabulky integration."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import InvalidAuthError, KalorickeTabulkyApi, KalorickeTabulkyError
from .const import (
    CONF_QUICK_FOODS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

ADD_QUICK_FOOD = "add_quick_food"
GENERAL = "general"
REMOVE_QUICK_FOOD = "remove_quick_food"
MEAL_TYPE_AUTO = "auto"
MEAL_TYPE_OPTIONS = (
    (MEAL_TYPE_AUTO, "Automatic by current time"),
    ("breakfast", "Breakfast"),
    ("morning_snack", "Morning snack"),
    ("lunch", "Lunch"),
    ("afternoon_snack", "Afternoon snack"),
    ("dinner", "Dinner"),
    ("second_dinner", "Second dinner"),
)


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


def _options_schema(current_interval: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
            ),
        }
    )


def _search_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("query"): str,
            vol.Required("kind", default="food"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="food", label="Food"),
                        selector.SelectOptionDict(value="drink", label="Drink"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def _select_food_schema(results: list[dict[str, Any]]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("food_guid"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=str(item["food_guid"]),
                            label=_search_result_label(item),
                        )
                        for item in results
                        if item.get("food_guid")
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _details_schema(
    *,
    title: str,
    unit_options: list[dict[str, Any]],
    selected_unit_guid: str | None,
) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required("title", default=title): str,
        vol.Required("amount", default=1.0): vol.All(
            vol.Coerce(float), _positive_number
        ),
        vol.Required("meal_type", default=MEAL_TYPE_AUTO): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=value, label=label)
                    for value, label in MEAL_TYPE_OPTIONS
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
    if unit_options:
        option_ids = {str(option["id"]) for option in unit_options if option.get("id")}
        default_unit = (
            selected_unit_guid
            if selected_unit_guid in option_ids
            else str(unit_options[0]["id"])
        )
        schema[vol.Required("unit_guid", default=default_unit)] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(
                        value=str(option["id"]), label=_unit_option_label(option)
                    )
                    for option in unit_options
                    if option.get("id")
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    else:
        schema[vol.Optional("unit")] = str
    return vol.Schema(schema)


def _remove_schema(quick_foods: list[dict[str, Any]]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("preset_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=str(item["id"]),
                            label=_quick_food_label(item),
                        )
                        for item in quick_foods
                        if item.get("id")
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


class KalorickeTabulkyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kaloricke Tabulky."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            api = KalorickeTabulkyApi(
                async_get_clientsession(self.hass), email, user_input[CONF_PASSWORD]
            )
            try:
                await api.authenticate()
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except KalorickeTabulkyError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(email)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return KalorickeTabulkyOptionsFlow(config_entry)


class KalorickeTabulkyOptionsFlow(config_entries.OptionsFlow):
    """Handle Kaloricke Tabulky options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._search_results: list[dict[str, Any]] = []
        self._selected_result: dict[str, Any] | None = None
        self._selected_options: dict[str, Any] | None = None
        self._selected_kind = "food"

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        menu_options = [GENERAL, ADD_QUICK_FOOD]
        if self._quick_foods:
            menu_options.append(REMOVE_QUICK_FOOD)
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage general options."""
        if user_input is not None:
            options = self._current_options
            options[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            return self.async_create_entry(title="", data=options)

        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id=GENERAL,
            data_schema=_options_schema(current_interval),
        )

    async def async_step_add_quick_food(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Search for a food preset to add."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = self._api()
            self._selected_kind = user_input["kind"]
            try:
                self._search_results = await api.async_search_food(
                    user_input["query"], self._selected_kind
                )
            except KalorickeTabulkyError:
                errors["base"] = "cannot_connect"
            else:
                self._search_results = [
                    item for item in self._search_results if item.get("food_guid")
                ]
                if not self._search_results:
                    errors["base"] = "no_food_found"
                else:
                    return await self.async_step_select_quick_food()

        return self.async_show_form(
            step_id=ADD_QUICK_FOOD,
            data_schema=_search_schema(),
            errors=errors,
        )

    async def async_step_select_quick_food(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select the exact food result."""
        errors: dict[str, str] = {}
        if user_input is not None:
            food_guid = user_input["food_guid"]
            self._selected_result = next(
                (
                    item
                    for item in self._search_results
                    if str(item.get("food_guid")) == food_guid
                ),
                None,
            )
            if self._selected_result is None:
                errors["base"] = "no_food_found"
            else:
                try:
                    self._selected_options = await self._api().async_get_food_options(
                        food_guid, date.today()
                    )
                except KalorickeTabulkyError:
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_quick_food_details()

        return self.async_show_form(
            step_id="select_quick_food",
            data_schema=_select_food_schema(self._search_results),
            errors=errors,
        )

    async def async_step_quick_food_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure the selected food preset."""
        if self._selected_result is None or self._selected_options is None:
            return await self.async_step_add_quick_food()

        unit_options = self._selected_options.get("unit_options") or []
        title = str(
            self._selected_options.get("title")
            or self._selected_result.get("title")
            or "Quick food"
        )

        if user_input is not None:
            unit_guid = user_input.get("unit_guid")
            unit = _unit_title(unit_options, unit_guid) or user_input.get("unit")
            meal_type = user_input.get("meal_type")
            quick_food = {
                "id": _preset_id(user_input["title"], self._selected_result["food_guid"]),
                "title": user_input["title"].strip(),
                "food_guid": self._selected_result["food_guid"],
                "kind": self._selected_kind,
                "amount": user_input["amount"],
                "unit": unit,
                "unit_guid": unit_guid,
                "meal_type": None if meal_type == MEAL_TYPE_AUTO else meal_type,
                "image_url": self._selected_options.get("image_url")
                or self._selected_result.get("image_url"),
            }
            options = self._current_options
            quick_foods = [
                item
                for item in options.get(CONF_QUICK_FOODS, [])
                if item.get("id") != quick_food["id"]
            ]
            quick_foods.append(quick_food)
            options[CONF_QUICK_FOODS] = quick_foods
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="quick_food_details",
            data_schema=_details_schema(
                title=title,
                unit_options=unit_options,
                selected_unit_guid=self._selected_options.get("unit_guid"),
            ),
        )

    async def async_step_remove_quick_food(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a configured quick food preset."""
        quick_foods = self._quick_foods
        if not quick_foods:
            return await self.async_step_init()

        if user_input is not None:
            options = self._current_options
            options[CONF_QUICK_FOODS] = [
                item
                for item in quick_foods
                if str(item.get("id")) != user_input["preset_id"]
            ]
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id=REMOVE_QUICK_FOOD,
            data_schema=_remove_schema(quick_foods),
        )

    @property
    def _current_options(self) -> dict[str, Any]:
        options = deepcopy(dict(self._config_entry.options))
        options.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        options.setdefault(CONF_QUICK_FOODS, [])
        return options

    @property
    def _quick_foods(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self._config_entry.options.get(CONF_QUICK_FOODS, [])
            if isinstance(item, dict)
        ]

    def _api(self) -> KalorickeTabulkyApi:
        coordinator = getattr(self._config_entry, "runtime_data", None)
        if coordinator is not None:
            return coordinator.api
        return KalorickeTabulkyApi(
            async_get_clientsession(self.hass),
            self._config_entry.data[CONF_EMAIL],
            self._config_entry.data[CONF_PASSWORD],
        )


def _positive_number(value: float) -> float:
    if value <= 0:
        raise vol.Invalid("Value must be positive")
    return value


def _search_result_label(item: dict[str, Any]) -> str:
    parts = [str(item.get("title") or item["food_guid"])]
    brand = item.get("brand_name")
    if brand:
        parts.append(str(brand))
    energy = item.get("energy")
    energy_unit = item.get("energy_unit")
    if energy is not None and energy_unit:
        parts.append(f"{energy:g} {energy_unit}")
    return " - ".join(parts)


def _unit_option_label(option: dict[str, Any]) -> str:
    title = str(option.get("title") or option["id"])
    multiplier = option.get("multiplier")
    if multiplier is None:
        return title
    return f"{title} ({multiplier:g})"


def _unit_title(options: list[dict[str, Any]], unit_guid: str | None) -> str | None:
    if unit_guid is None:
        return None
    for option in options:
        if str(option.get("id")) == unit_guid:
            title = option.get("title")
            return str(title) if title else None
    return None


def _quick_food_label(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("food_guid") or "Quick food")
    amount = item.get("amount")
    unit = item.get("unit")
    if amount is None:
        return title
    return f"{title} - {amount:g} {unit}" if unit else f"{title} - {amount:g}"


def _preset_id(title: str, food_guid: str) -> str:
    slug = title.lower()
    slug = slug.translate(str.maketrans("áčďéěíňóřšťúůýž", "acdeeinorstuuyz"))
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    suffix = re.sub(r"[^a-zA-Z0-9]+", "", str(food_guid))[-8:]
    return f"{slug or 'quick_food'}_{suffix}"
