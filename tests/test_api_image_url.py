"""Regression tests for Kaloricke Tabulky image URL normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "custom_components" / "kaloricke_tabulky" / "api.py"


def _load_api():
    """Load api.py without importing the integration package __init__."""
    spec = importlib.util.spec_from_file_location(
        "custom_components.kaloricke_tabulky.api", API
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ImageUrlNormalizationTest(unittest.TestCase):
    """Cover image fields returned by the KT autocomplete and add-form APIs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.api = _load_api()

    def test_search_result_builds_thumb_url_from_has_image(self) -> None:
        result = self.api._normalize_search_result(
            {
                "clazz": "foodstuff",
                "id": "afdaf7fb2de730aa",
                "url": "latte-macchiato",
                "title": "Latte macchiato",
                "value": "44",
                "energyUnit": "kcal",
                "hasImage": True,
            }
        )

        self.assertEqual(
            result["image_url"],
            "https://www.kaloricketabulky.cz/file/image/thumb/foodstuff/afdaf7fb2de730aa",
        )
        self.assertTrue(result["has_image"])
        self.assertEqual(result["image_class"], "foodstuff")

    def test_search_result_prefers_explicit_image_url(self) -> None:
        result = self.api._normalize_search_result(
            {
                "clazz": "foodstuff",
                "id": "afdaf7fb2de730aa",
                "title": "Latte macchiato",
                "hasImage": True,
                "photoThumbGastroPartnerUrl": "/brand/thumb.jpg",
            }
        )

        self.assertEqual(
            result["image_url"],
            "https://www.kaloricketabulky.cz/brand/thumb.jpg",
        )

    def test_food_options_builds_thumb_url_from_form_guid(self) -> None:
        result = self.api._normalize_food_options(
            {
                "foodstuffGuid": "afdaf7fb2de730aa",
                "title": "Latte macchiato",
                "unitGuid": "dd4643ebe92672f7",
                "hasImage": True,
                "unitOptions": [
                    {
                        "id": "dd4643ebe92672f7",
                        "title": "porce",
                        "multiplier": "1",
                    }
                ],
            }
        )

        self.assertEqual(
            result["image_url"],
            "https://www.kaloricketabulky.cz/file/image/thumb/foodstuff/afdaf7fb2de730aa",
        )
        self.assertTrue(result["has_image"])
        self.assertEqual(result["image_class"], "foodstuff")


if __name__ == "__main__":
    unittest.main()
