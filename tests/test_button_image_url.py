"""Regression tests for quick-food button image attributes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUTTON = ROOT / "custom_components" / "kaloricke_tabulky" / "button.py"


def _load_button():
    """Load button.py without importing the integration package __init__."""
    button_component = types.ModuleType("homeassistant.components.button")
    button_component.ButtonEntity = object

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object

    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = object

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        def __init__(self, coordinator):  # noqa: D107
            self.coordinator = coordinator

        def __class_getitem__(cls, item):  # noqa: D105
            return cls

    update_coordinator.CoordinatorEntity = CoordinatorEntity

    dt_util = types.ModuleType("homeassistant.util.dt")
    dt_util.now = lambda: None

    util = types.ModuleType("homeassistant.util")
    util.dt = dt_util

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = types.ModuleType("custom_components.kaloricke_tabulky")
    package.__path__ = [str(ROOT / "custom_components" / "kaloricke_tabulky")]

    api = types.ModuleType("custom_components.kaloricke_tabulky.api")
    api.KalorickeTabulkyError = type("KalorickeTabulkyError", (Exception,), {})

    const = types.ModuleType("custom_components.kaloricke_tabulky.const")
    const.CONF_QUICK_FOODS = "quick_foods"
    const.DOMAIN = "kaloricke_tabulky"

    coordinator = types.ModuleType("custom_components.kaloricke_tabulky.coordinator")
    coordinator.KalorickeTabulkyCoordinator = object

    old_modules = {
        name: sys.modules.get(name)
        for name in (
            "homeassistant.components.button",
            "homeassistant.config_entries",
            "homeassistant.core",
            "homeassistant.exceptions",
            "homeassistant.helpers.device_registry",
            "homeassistant.helpers.entity_platform",
            "homeassistant.helpers.update_coordinator",
            "homeassistant.util",
            "homeassistant.util.dt",
            "custom_components",
            "custom_components.kaloricke_tabulky",
            "custom_components.kaloricke_tabulky.api",
            "custom_components.kaloricke_tabulky.const",
            "custom_components.kaloricke_tabulky.coordinator",
        )
    }
    sys.modules.update(
        {
            "homeassistant.components.button": button_component,
            "homeassistant.config_entries": config_entries,
            "homeassistant.core": core,
            "homeassistant.exceptions": exceptions,
            "homeassistant.helpers.device_registry": device_registry,
            "homeassistant.helpers.entity_platform": entity_platform,
            "homeassistant.helpers.update_coordinator": update_coordinator,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt_util,
            "custom_components": custom_components,
            "custom_components.kaloricke_tabulky": package,
            "custom_components.kaloricke_tabulky.api": api,
            "custom_components.kaloricke_tabulky.const": const,
            "custom_components.kaloricke_tabulky.coordinator": coordinator,
        }
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "custom_components.kaloricke_tabulky.button", BUTTON
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


class ButtonImageUrlTest(unittest.TestCase):
    """Cover entity-picture fallback for existing presets without image_url."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.button = _load_button()

    def test_existing_preset_without_image_url_gets_kt_thumb_url(self) -> None:
        self.assertEqual(
            self.button._preset_image_url(
                {
                    "food_guid": "afdaf7fb2de730aa",
                    "title": "Latte macchiato",
                }
            ),
            "https://www.kaloricketabulky.cz/file/image/thumb/foodstuff/afdaf7fb2de730aa",
        )

    def test_explicit_image_url_is_kept(self) -> None:
        self.assertEqual(
            self.button._preset_image_url(
                {
                    "food_guid": "afdaf7fb2de730aa",
                    "image_url": "https://example.test/image.jpg",
                }
            ),
            "https://example.test/image.jpg",
        )

    def test_explicit_no_image_is_kept(self) -> None:
        self.assertIsNone(
            self.button._preset_image_url(
                {
                    "food_guid": "afdaf7fb2de730aa",
                    "has_image": False,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
