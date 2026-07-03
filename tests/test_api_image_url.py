"""Regression tests for Kaloricke Tabulky image URL normalization."""

from __future__ import annotations

import importlib.util
from datetime import date
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


class RecipeServingRecordTest(unittest.IsolatedAsyncioTestCase):
    """Cover custom recipe diary writes through the recipe endpoint."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.api_module = _load_api()

    async def test_record_recipe_serving_uses_recipe_endpoint_for_meal_class(self) -> None:
        client = _FakeKalorickeTabulkyApi(self.api_module)

        result = await client.async_record_food(
            food_guid="recipe-guid",
            item_class="meal",
            amount=1,
            target_date=date(2026, 7, 2),
            target_time="12:30",
        )

        self.assertEqual(result["message"], "Úspěšně zapsáno!")
        self.assertEqual(result["title"], "Boloňské špagety")
        self.assertEqual(result["unit_guid"], "portion-guid")
        self.assertEqual(result["multiplier"], 1)
        self.assertEqual(
            [call[1] for call in client.calls],
            [
                "https://www.kaloricketabulky.cz/user/meal/add/form/recipe-guid?format=json",
                "https://www.kaloricketabulky.cz/user/recipe/add?format=json",
            ],
        )

    async def test_record_recipe_serving_scales_counts_with_explicit_unit_guid(self) -> None:
        client = _FakeKalorickeTabulkyApi(self.api_module)

        result = await client.async_record_food(
            food_guid="recipe-guid",
            item_class="meal",
            amount=1,
            unit="porce",
            unit_guid="portion-guid",
            target_date=date(2026, 7, 2),
            target_time="12:30",
        )

        self.assertEqual(result["message"], "Úspěšně zapsáno!")
        self.assertEqual(result["unit_guid"], "portion-guid")
        self.assertEqual(result["multiplier"], 1)
        self.assertEqual(
            [call[1] for call in client.calls],
            [
                "https://www.kaloricketabulky.cz/user/meal/add/form/recipe-guid?format=json",
                "https://www.kaloricketabulky.cz/user/recipe/add?format=json",
            ],
        )

    async def test_record_recipe_serving_falls_back_from_empty_food_form(self) -> None:
        client = _FakeKalorickeTabulkyApi(self.api_module, empty_food_form=True)

        result = await client.async_record_food(
            food_guid="recipe-guid",
            amount=1,
            target_date=date(2026, 7, 2),
            target_time="12:30",
        )

        self.assertEqual(result["message"], "Úspěšně zapsáno!")
        self.assertEqual(
            [call[1] for call in client.calls],
            [
                "https://www.kaloricketabulky.cz/user/foodstuff/add/form/recipe-guid/02.07.2026/get?format=json",
                "https://www.kaloricketabulky.cz/user/meal/add/form/recipe-guid?format=json",
                "https://www.kaloricketabulky.cz/user/recipe/add?format=json",
            ],
        )


class _FakeKalorickeTabulkyApi:
    def __init__(self, api_module, *, empty_food_form: bool = False) -> None:
        self._api = api_module
        self._client = api_module.KalorickeTabulkyApi(session=None, email="", password="")
        self._client._request_with_reauth = self._request_with_reauth
        self.calls = []
        self._empty_food_form = empty_food_form

    async def async_record_food(self, **kwargs):
        return await self._client.async_record_food(**kwargs)

    async def _request_with_reauth(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if "user/foodstuff/add/form" in url and self._empty_food_form:
            return {"data": {"title": None, "unitGuid": None, "unitOptions": []}}
        if "user/meal/add/form" in url:
            return {
                "data": {
                    "guid": "recipe-guid",
                    "title": "Boloňské špagety",
                    "selectedUnitGuid": "portion-guid",
                    "selectedUnitMultiplier": 1,
                    "diaryTimeGuid": "1",
                    "portionsMax": "4",
                    "units": [
                        {
                            "id": "portion-guid",
                            "title": "porce",
                            "multiplier": "-2",
                        }
                    ],
                    "foodstuff": [
                        {
                            "selected": True,
                            "count": 100,
                            "unitCount": 100,
                            "selectedUnitGuid": "g",
                            "units": [{"id": "g", "title": "1 g", "multiplier": "1"}],
                        },
                        {
                            "selected": True,
                            "countOriginal": "20",
                            "count": 20,
                            "unitCountOriginal": "20",
                            "unitCount": 20,
                            "selectedUnitGuid": "g",
                            "units": [{"id": "g", "title": "1 g", "multiplier": "1"}],
                        },
                        {
                            "selected": True,
                            "countOriginal": "0.3",
                            "count": 0.3,
                            "unitCountOriginal": "0.3",
                            "unitCount": 0.3,
                            "selectedUnitGuid": "g",
                            "units": [{"id": "g", "title": "1 g", "multiplier": "1"}],
                        },
                    ],
                }
            }
        if "user/recipe/add" in url:
            payload = kwargs["json"]
            assert payload["date"] == "02.07.2026"
            assert payload["time"] == "12:30"
            assert payload["selectedUnitMultiplier"] == 1
            assert payload["foodstuff"][0]["count"] == 25
            assert payload["foodstuff"][0]["unitCount"] == 25
            assert payload["foodstuff"][1]["count"] == 5
            assert payload["foodstuff"][1]["unitCount"] == 5
            assert payload["foodstuff"][2]["count"] == 0.1
            assert payload["foodstuff"][2]["unitCount"] == 0.1
            return {"message": "Úspěšně zapsáno!"}
        raise AssertionError(f"Unexpected request: {method} {url}")


if __name__ == "__main__":
    unittest.main()
