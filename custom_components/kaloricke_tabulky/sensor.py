"""Sensor platform for the Kaloricke Tabulky integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SummaryMetric
from .const import DOMAIN
from .coordinator import KalorickeTabulkyCoordinator

ENERGY_UNITS = {"kcal", "kj", "wh", "kwh"}
MASS_UNITS = {"g", "kg", "mg"}
VOLUME_UNITS = {"ml", "l"}
KNOWN_SUMMARY_SENSORS = (
    (
        "energy",
        (
            "energy",
            "energy_kcal",
            "energykcal",
            "energie",
            "energeticka_hodnota",
            "kcal",
            "calorie",
            "calories",
            "total",
        ),
        "kcal",
    ),
    ("body_weight", ("cilova_hmotnost", "weight"), "kg"),
    ("protein", ("protein", "proteins", "bilkoviny"), "g"),
    ("carbohydrates", ("carbohydrate", "carbohydrates", "carbs", "sacharidy"), "g"),
    ("fat", ("fat", "fats", "tuky"), "g"),
    ("fiber", ("fiber", "fibre", "vlaknina"), "g"),
    ("sugar", ("sugar", "sugars", "cukry", "z_toho_cukry"), "g"),
    ("salt", ("salt", "sul"), "g"),
    ("water", ("water", "voda", "pitny_rezim"), "l"),
    ("activity_energy_total", ("activity_energy_total",), "kcal"),
    ("activity_level_energy", ("activity_level_energy",), "kcal"),
    ("energy_output_total", ("energy_output_total",), "kcal"),
    ("energy_intake_maintenance", ("energy_intake_maintenance",), "kcal"),
    ("energy_deficit", ("energy_deficit",), "kcal"),
    ("energy_target", ("energy_target",), "kcal"),
    ("basal_metabolism", ("basal_metabolism",), "kcal"),
    ("energy_intake_rest", ("energy_intake_rest",), "kcal"),
)
TRANSLATED_METRIC_KEYS = {
    "activity_energy_total",
    "activity_level_energy",
    "basal_metabolism",
    "bilkoviny",
    "body_weight",
    "calorie",
    "calories",
    "carbohydrate",
    "carbohydrates",
    "carbs",
    "cukry",
    "energy",
    "energy_deficit",
    "energy_kcal",
    "energy_intake_maintenance",
    "energy_intake_rest",
    "energy_output_total",
    "energy_target",
    "energykcal",
    "energie",
    "energeticka_hodnota",
    "fat",
    "fats",
    "fiber",
    "fibre",
    "kcal",
    "kj",
    "mastne_kyseliny_nasycene",
    "nasycene_mastne_kyseliny",
    "pitny_rezim",
    "protein",
    "proteins",
    "sacharidy",
    "salt",
    "sugars",
    "sugar",
    "sul",
    "tuky",
    "total",
    "vlaknina",
    "voda",
    "water",
    "weight",
    "z_toho_cukry",
}


@dataclass(slots=True, frozen=True)
class SummarySensorDefinition:
    """Definition for a stable known summary sensor."""

    key: str
    source_keys: tuple[str, ...]
    unit: str | None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kaloricke Tabulky sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [LatestWeightSensor(entry, coordinator)]
    known_definitions = [
        SummarySensorDefinition(key, aliases, unit)
        for key, aliases, unit in KNOWN_SUMMARY_SENSORS
    ]
    entities.extend(
        KnownSummaryMetricSensor(entry, coordinator, definition)
        for definition in known_definitions
    )
    known_source_keys = {
        source_key
        for definition in known_definitions
        for source_key in definition.source_keys
    }
    if coordinator.data:
        entities.extend(
            SummaryMetricSensor(entry, coordinator, metric)
            for metric in coordinator.data.metrics.values()
            if metric.key not in known_source_keys
        )
    async_add_entities(entities)


class LatestWeightSensor(CoordinatorEntity[KalorickeTabulkyCoordinator], SensorEntity):
    """Sensor exposing the latest known weight."""

    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "latest_weight"

    def __init__(
        self, entry: ConfigEntry, coordinator: KalorickeTabulkyCoordinator
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_latest_weight"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Kaloricke Tabulky",
            name=self._entry.title,
        )

    @property
    def native_value(self) -> float | None:
        """Return the latest weight value."""
        if not self.coordinator.data or not self.coordinator.data.weight_records:
            return None
        return self.coordinator.data.weight_records[-1].weight

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional weight record details."""
        if not self.coordinator.data or not self.coordinator.data.weight_records:
            return {"records": []}

        latest = self.coordinator.data.weight_records[-1]
        return {
            "date": latest.date_label,
            "records": [
                {"date": record.date_label, "weight": record.weight}
                for record in self.coordinator.data.weight_records
            ],
        }


class SummaryMetricSensor(CoordinatorEntity[KalorickeTabulkyCoordinator], SensorEntity):
    """Sensor exposing a numeric summary metric."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: KalorickeTabulkyCoordinator,
        metric: SummaryMetric,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._metric_key = metric.key
        self._attr_unique_id = f"{entry.entry_id}_{metric.key}"
        if metric.key in TRANSLATED_METRIC_KEYS:
            self._attr_translation_key = metric.key
        else:
            self._attr_name = metric.name
        self._attr_native_unit_of_measurement = _native_unit(metric.unit)
        self._attr_device_class = _device_class(metric.unit)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Kaloricke Tabulky",
            name=self._entry.title,
        )

    @property
    def native_value(self) -> float | None:
        """Return the metric value."""
        if not self.coordinator.data:
            return None
        metric = self.coordinator.data.metrics.get(self._metric_key)
        return None if metric is None else metric.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return goal and percentage details."""
        if not self.coordinator.data:
            return {}
        metric = self.coordinator.data.metrics.get(self._metric_key)
        if metric is None:
            return {}
        return _metric_attributes(metric)


class KnownSummaryMetricSensor(
    CoordinatorEntity[KalorickeTabulkyCoordinator], SensorEntity
):
    """Stable sensor for a known daily summary metric."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: KalorickeTabulkyCoordinator,
        definition: SummarySensorDefinition,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._definition = definition
        self._attr_unique_id = f"{entry.entry_id}_{definition.key}"
        self._attr_translation_key = definition.key
        self._attr_native_unit_of_measurement = _native_unit(definition.unit)
        self._attr_device_class = _device_class(definition.unit)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Kaloricke Tabulky",
            name=self._entry.title,
        )

    @property
    def native_value(self) -> float | None:
        """Return the first matching summary metric value."""
        metric = self._metric
        return None if metric is None else metric.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return goal and percentage details."""
        metric = self._metric
        if metric is None:
            return {}
        return _metric_attributes(metric)

    @property
    def _metric(self) -> SummaryMetric | None:
        """Return the first matching summary metric."""
        if not self.coordinator.data:
            return None
        for key in self._definition.source_keys:
            metric = self.coordinator.data.metrics.get(key)
            if metric is not None:
                return metric
        return None


def _metric_attributes(metric: SummaryMetric) -> dict[str, Any]:
    attributes: dict[str, Any] = {"source_key": metric.key}
    if metric.goal is not None:
        attributes["goal"] = metric.goal
    if metric.percent is not None:
        attributes["percent"] = metric.percent
    return attributes


def _native_unit(unit: str | None) -> str | None:
    if unit is None:
        return None

    normalized = unit.strip().lower()
    if normalized in {"kcal", "kj", "kg", "g", "mg", "l", "ml", "%"}:
        return unit
    return unit


def _device_class(unit: str | None) -> SensorDeviceClass | None:
    if unit is None:
        return None

    normalized = unit.strip().lower()
    if normalized in ENERGY_UNITS:
        return SensorDeviceClass.ENERGY
    if normalized in MASS_UNITS:
        return SensorDeviceClass.WEIGHT
    if normalized in VOLUME_UNITS:
        return SensorDeviceClass.VOLUME
    return None
