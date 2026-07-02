"""Regression tests for sensor metadata accepted by Home Assistant."""

from __future__ import annotations

import importlib.util
from enum import Enum
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
SENSOR = ROOT / "custom_components" / "kaloricke_tabulky" / "sensor.py"


def _load_sensor():
    """Load sensor.py without importing the integration package __init__."""
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = types.ModuleType("custom_components.kaloricke_tabulky")
    package.__path__ = [str(ROOT / "custom_components" / "kaloricke_tabulky")]

    api = types.ModuleType("custom_components.kaloricke_tabulky.api")
    api.SummaryMetric = type("SummaryMetric", (), {})

    const = types.ModuleType("custom_components.kaloricke_tabulky.const")
    const.DOMAIN = "kaloricke_tabulky"

    coordinator = types.ModuleType("custom_components.kaloricke_tabulky.coordinator")
    coordinator.KalorickeTabulkyCoordinator = type(
        "KalorickeTabulkyCoordinator", (), {}
    )

    sensor_component = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass(Enum):
        ENERGY = "energy"
        VOLUME = "volume"
        WEIGHT = "weight"

    class SensorStateClass(Enum):
        MEASUREMENT = "measurement"

    class SensorEntity:
        pass

    sensor_component.SensorDeviceClass = SensorDeviceClass
    sensor_component.SensorEntity = SensorEntity
    sensor_component.SensorStateClass = SensorStateClass

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object

    ha_const = types.ModuleType("homeassistant.const")

    class UnitOfMass:
        KILOGRAMS = "kg"

    ha_const.UnitOfMass = UnitOfMass

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = object

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        def __init_subclass__(cls, **kwargs):  # noqa: D105
            super().__init_subclass__()

        @classmethod
        def __class_getitem__(cls, item):  # noqa: D105
            return cls

    update_coordinator.CoordinatorEntity = CoordinatorEntity

    old_modules = {
        name: sys.modules.get(name)
        for name in (
            "custom_components",
            "custom_components.kaloricke_tabulky",
            "custom_components.kaloricke_tabulky.api",
            "custom_components.kaloricke_tabulky.const",
            "custom_components.kaloricke_tabulky.coordinator",
            "homeassistant.components.sensor",
            "homeassistant.config_entries",
            "homeassistant.const",
            "homeassistant.core",
            "homeassistant.helpers.device_registry",
            "homeassistant.helpers.entity_platform",
            "homeassistant.helpers.update_coordinator",
        )
    }
    sys.modules.update(
        {
            "custom_components": custom_components,
            "custom_components.kaloricke_tabulky": package,
            "custom_components.kaloricke_tabulky.api": api,
            "custom_components.kaloricke_tabulky.const": const,
            "custom_components.kaloricke_tabulky.coordinator": coordinator,
            "homeassistant.components.sensor": sensor_component,
            "homeassistant.config_entries": config_entries,
            "homeassistant.const": ha_const,
            "homeassistant.core": core,
            "homeassistant.helpers.device_registry": device_registry,
            "homeassistant.helpers.entity_platform": entity_platform,
            "homeassistant.helpers.update_coordinator": update_coordinator,
        }
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "custom_components.kaloricke_tabulky.sensor", SENSOR
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in old_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class SensorMetadataTest(unittest.TestCase):
    """Cover HA sensor metadata combinations reported in system logs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sensor = _load_sensor()

    def test_nutrition_energy_sensors_keep_measurement_state_class(self) -> None:
        self.assertIsNone(self.sensor._device_class("kcal"))
        self.assertIsNone(self.sensor._device_class("kJ"))
        self.assertIs(
            self.sensor._state_class("kcal"),
            self.sensor.SensorStateClass.MEASUREMENT,
        )
        self.assertIs(
            self.sensor._state_class("kJ"),
            self.sensor.SensorStateClass.MEASUREMENT,
        )

    def test_non_energy_numeric_sensors_keep_measurement_state_class(self) -> None:
        self.assertIs(
            self.sensor._state_class("g"), self.sensor.SensorStateClass.MEASUREMENT
        )
        self.assertIs(
            self.sensor._state_class("l"), self.sensor.SensorStateClass.MEASUREMENT
        )


if __name__ == "__main__":
    unittest.main()
