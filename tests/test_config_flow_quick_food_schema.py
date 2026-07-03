"""Regression tests for quick food options-flow schemas."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

import voluptuous as vol
import voluptuous_serialize


ROOT = Path(__file__).resolve().parents[1]
CONFIG_FLOW = ROOT / "custom_components" / "kaloricke_tabulky" / "config_flow.py"


def _load_config_flow():
    """Load config_flow.py without importing the integration package __init__."""
    # Import the real selector before stubbing heavier Home Assistant modules.
    from homeassistant.helpers import selector as _selector  # noqa: F401

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = types.ModuleType("custom_components.kaloricke_tabulky")
    package.__path__ = [str(ROOT / "custom_components" / "kaloricke_tabulky")]

    api = types.ModuleType("custom_components.kaloricke_tabulky.api")
    api.InvalidAuthError = type("InvalidAuthError", (Exception,), {})
    api.KalorickeTabulkyError = type("KalorickeTabulkyError", (Exception,), {})
    api.KalorickeTabulkyApi = type("KalorickeTabulkyApi", (), {})

    const = types.ModuleType("custom_components.kaloricke_tabulky.const")
    const.CONF_QUICK_FOODS = "quick_foods"
    const.CONF_SCAN_INTERVAL = "scan_interval"
    const.DEFAULT_SCAN_INTERVAL = 240
    const.DOMAIN = "kaloricke_tabulky"
    const.MIN_SCAN_INTERVAL = 15

    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):  # noqa: D105
            super().__init_subclass__()

    class OptionsFlow:
        pass

    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    config_entries.ConfigEntry = object
    config_entries.ConfigFlowResult = dict

    core = types.ModuleType("homeassistant.core")
    core.callback = lambda func: func

    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: None

    old_modules = {
        name: sys.modules.get(name)
        for name in (
            "custom_components",
            "custom_components.kaloricke_tabulky",
            "custom_components.kaloricke_tabulky.api",
            "custom_components.kaloricke_tabulky.const",
            "homeassistant.config_entries",
            "homeassistant.core",
            "homeassistant.helpers.aiohttp_client",
        )
    }
    sys.modules.update(
        {
            "custom_components": custom_components,
            "custom_components.kaloricke_tabulky": package,
            "custom_components.kaloricke_tabulky.api": api,
            "custom_components.kaloricke_tabulky.const": const,
            "homeassistant.config_entries": config_entries,
            "homeassistant.core": core,
            "homeassistant.helpers.aiohttp_client": aiohttp_client,
        }
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "custom_components.kaloricke_tabulky.config_flow", CONFIG_FLOW
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


class QuickFoodSelectSchemaTest(unittest.TestCase):
    """Cover cached select-field variants seen in Home Assistant options flow."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config_flow = _load_config_flow()
        cls.schema = cls.config_flow._select_food_schema(
            [
                {
                    "food_guid": "abc123",
                    "title": "Test food",
                    "brand_name": "Brand",
                    "energy": 42,
                    "energy_unit": "kcal",
                }
            ]
        )

    def test_accepts_current_food_guid_field(self) -> None:
        self.assertEqual(self.schema({"food_guid": "abc123"})["food_guid"], "abc123")

    def test_accepts_cached_selected_food_field(self) -> None:
        validated = self.schema({"selected_food": "abc123"})
        self.assertEqual(validated["selected_food"], "abc123")
        self.assertNotIn("food_guid", validated)

    def test_accepts_both_cached_and_current_fields(self) -> None:
        validated = self.schema({"food_guid": "abc123", "selected_food": "abc123"})
        self.assertEqual(validated["food_guid"], "abc123")
        self.assertEqual(validated["selected_food"], "abc123")

    def test_rejects_invalid_current_food_guid(self) -> None:
        with self.assertRaises(vol.MultipleInvalid):
            self.schema({"food_guid": "missing"})

    def test_does_not_default_to_first_result(self) -> None:
        self.assertEqual(self.schema({}), {})


class QuickFoodDetailsSchemaTest(unittest.TestCase):
    """Cover Home Assistant frontend schema serialization for details step."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config_flow = _load_config_flow()

    def test_details_schema_is_serializable_for_frontend(self) -> None:
        from homeassistant.helpers import config_validation as cv

        schema = self.config_flow._details_schema(
            title="Test food",
            unit_options=[{"id": "g", "title": "g", "multiplier": 1}],
            selected_unit_guid="g",
        )

        converted = voluptuous_serialize.convert(
            schema, custom_serializer=cv.custom_serializer
        )

        fields = {field["name"]: field for field in converted}
        self.assertEqual(fields["amount"]["selector"]["number"]["mode"], "box")
        self.assertEqual(fields["amount"]["selector"]["number"]["step"], "any")
        self.assertGreater(fields["amount"]["selector"]["number"]["min"], 0)
        self.assertIn("category", fields)
        category_options = fields["category"]["selector"]["select"]["options"]
        self.assertIn(
            {"value": "alcohol", "label": "Alcohol"},
            category_options,
        )

    def test_details_schema_rejects_non_positive_amount(self) -> None:
        schema = self.config_flow._details_schema(
            title="Test food",
            unit_options=[],
            selected_unit_guid=None,
        )

        with self.assertRaises(vol.MultipleInvalid):
            schema({"title": "Test food", "amount": 0, "meal_type": "auto"})

    def test_details_schema_accepts_alcohol_category(self) -> None:
        schema = self.config_flow._details_schema(
            title="Pivo",
            unit_options=[],
            selected_unit_guid=None,
        )

        validated = schema(
            {
                "title": "Pivo",
                "amount": 1,
                "meal_type": "auto",
                "category": "alcohol",
            }
        )

        self.assertEqual(validated["category"], "alcohol")


class UpdateCredentialsSchemaTest(unittest.TestCase):
    """Cover password update options-flow schema."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config_flow = _load_config_flow()

    def test_credentials_schema_defaults_email_and_requires_password(self) -> None:
        schema = self.config_flow._credentials_schema("tom@example.test")

        validated = schema({"password": "new-password"})

        self.assertEqual(validated["email"], "tom@example.test")
        self.assertEqual(validated["password"], "new-password")


class ImportCustomRecipeButtonsTest(unittest.TestCase):
    """Cover custom recipe quick-button import helpers."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config_flow = _load_config_flow()

    def test_import_creates_one_portion_recipe_button(self) -> None:
        imported = self.config_flow._import_custom_recipe_buttons(
            [],
            [
                {
                    "food_guid": "recipe-guid",
                    "title": "Špenátový krém (Mealie)",
                    "image_class": "meal",
                }
            ],
            {
                "recipe-guid": {
                    "title": "Špenátový krém (Mealie)",
                    "unit_guid": "portion-guid",
                    "unit_options": [
                        {"id": "portion-guid", "title": "porce", "multiplier": -2}
                    ],
                    "has_image": True,
                    "image_class": "meal",
                }
            },
        )

        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0]["food_guid"], "recipe-guid")
        self.assertEqual(imported[0]["item_class"], "meal")
        self.assertEqual(imported[0]["amount"], 1.0)
        self.assertEqual(imported[0]["unit"], "porce")
        self.assertEqual(imported[0]["unit_guid"], "portion-guid")
        self.assertEqual(imported[0]["image_class"], "meal")
        self.assertIsNone(imported[0]["image_url"])
        self.assertTrue(imported[0]["has_image"])

    def test_import_keeps_recipe_button_image_fallback_enabled(self) -> None:
        imported = self.config_flow._import_custom_recipe_buttons(
            [],
            [
                {
                    "food_guid": "recipe-guid",
                    "title": "Špenátový krém (Mealie)",
                    "has_image": False,
                    "image_class": "meal",
                }
            ],
            {
                "recipe-guid": {
                    "title": "Špenátový krém (Mealie)",
                    "unit_guid": "portion-guid",
                    "unit_options": [
                        {"id": "portion-guid", "title": "porce", "multiplier": -2}
                    ],
                    "has_image": False,
                    "image_class": "meal",
                }
            },
        )

        self.assertIsNone(imported[0]["image_url"])
        self.assertIsNone(imported[0]["has_image"])
        self.assertEqual(imported[0]["image_class"], "meal")

    def test_import_skips_existing_recipe_guid(self) -> None:
        existing = {
            "id": "existing",
            "food_guid": "recipe-guid",
            "title": "Already here",
        }

        imported = self.config_flow._import_custom_recipe_buttons(
            [existing],
            [{"food_guid": "recipe-guid", "title": "Špenátový krém (Mealie)"}],
        )

        self.assertEqual(imported, [existing])

    def test_import_falls_back_to_default_portion_unit(self) -> None:
        imported = self.config_flow._import_custom_recipe_buttons(
            [],
            [{"food_guid": "recipe-guid", "title": "Bez detailu"}],
        )

        self.assertEqual(imported[0]["unit"], "porce")
        self.assertEqual(imported[0]["unit_guid"], "0000000000000004")


if __name__ == "__main__":
    unittest.main()
