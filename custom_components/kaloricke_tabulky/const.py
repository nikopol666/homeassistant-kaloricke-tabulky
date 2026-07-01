"""Constants for the Kaloricke Tabulky integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "kaloricke_tabulky"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_QUICK_FOODS = "quick_foods"

DEFAULT_SCAN_INTERVAL = 240
MIN_SCAN_INTERVAL = 15
DEFAULT_SCAN_INTERVAL_DELTA = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

PLATFORMS = ["sensor"]

SERVICE_RECORD_WEIGHT = "record_weight"
SERVICE_SEARCH_FOOD = "search_food"
SERVICE_RECORD_FOOD = "record_food"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_WEIGHT = "weight"
ATTR_DATE = "date"
ATTR_QUERY = "query"
ATTR_KIND = "kind"
ATTR_PAGE = "page"
ATTR_FOOD_GUID = "food_guid"
ATTR_AMOUNT = "amount"
ATTR_UNIT = "unit"
ATTR_UNIT_GUID = "unit_guid"
ATTR_TIME = "time"
ATTR_MEAL_TYPE = "meal_type"
