"""Constants for the Kaloricke Tabulky integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "kaloricke_tabulky"

CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 240
MIN_SCAN_INTERVAL = 15
DEFAULT_SCAN_INTERVAL_DELTA = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

PLATFORMS = ["sensor"]

SERVICE_RECORD_WEIGHT = "record_weight"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_WEIGHT = "weight"
ATTR_DATE = "date"
