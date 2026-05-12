"""API client for Kaloricke Tabulky."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import md5
from http.cookies import SimpleCookie
import re
from typing import Any

from aiohttp import ClientResponse, ClientSession

LOGIN_URL = "https://www.kaloricketabulky.cz/login/create?format=json"
SUMMARY_URL = "https://www.kaloricketabulky.cz/statistic/summary/{date}/get?format=json"
DIARY_SUMMARY_URL = "https://www.kaloricketabulky.cz/user/diary/summary/{date}/get?format=json"
RECORD_WEIGHT_URL = "https://www.kaloricketabulky.cz/user/weight/add?format=json&="


class KalorickeTabulkyError(Exception):
    """Base error for Kaloricke Tabulky API failures."""


class InvalidAuthError(KalorickeTabulkyError):
    """Raised when credentials are rejected."""


class SessionExpiredError(KalorickeTabulkyError):
    """Raised when the API session is no longer authenticated."""


@dataclass(slots=True, frozen=True)
class WeightRecord:
    """A weight record returned by Kaloricke Tabulky."""

    date_label: str
    weight: float


@dataclass(slots=True, frozen=True)
class SummaryMetric:
    """A numeric metric returned by the summary endpoint."""

    key: str
    name: str
    value: float
    unit: str | None = None
    goal: float | None = None
    percent: int | None = None


@dataclass(slots=True, frozen=True)
class SummaryData:
    """Parsed summary data returned by Kaloricke Tabulky."""

    weight_records: list[WeightRecord]
    metrics: dict[str, SummaryMetric]
    raw: dict[str, Any]


KNOWN_METRICS: dict[str, tuple[str, str | None]] = {
    "energy": ("Energy", "kcal"),
    "energy_kcal": ("Energy", "kcal"),
    "energykcal": ("Energy", "kcal"),
    "energie": ("Energy", "kcal"),
    "energeticka_hodnota": ("Energy", "kcal"),
    "calorie": ("Energy", "kcal"),
    "calories": ("Energy", "kcal"),
    "kcal": ("Energy", "kcal"),
    "kj": ("Energy", "kJ"),
    "total": ("Energy", "kcal"),
    "activity_energy_total": ("Activity energy", "kcal"),
    "activity_level_energy": ("Activity level energy", "kcal"),
    "basal_metabolism": ("Basal metabolism", "kcal"),
    "cilova_hmotnost": ("Body weight", "kg"),
    "energy_deficit": ("Energy deficit", "kcal"),
    "energy_intake_maintenance": ("Maintenance intake", "kcal"),
    "energy_intake_rest": ("Energy remaining", "kcal"),
    "energy_output_total": ("Energy output total", "kcal"),
    "energy_target": ("Energy target", "kcal"),
    "protein": ("Protein", "g"),
    "proteins": ("Protein", "g"),
    "bilkoviny": ("Protein", "g"),
    "carbohydrate": ("Carbohydrates", "g"),
    "carbohydrates": ("Carbohydrates", "g"),
    "carbs": ("Carbohydrates", "g"),
    "sacharidy": ("Carbohydrates", "g"),
    "fat": ("Fat", "g"),
    "fats": ("Fat", "g"),
    "mastne_kyseliny_nasycene": ("Saturated fat", "g"),
    "nasycene_mastne_kyseliny": ("Saturated fat", "g"),
    "tuky": ("Fat", "g"),
    "fiber": ("Fiber", "g"),
    "fibre": ("Fiber", "g"),
    "vlaknina": ("Fiber", "g"),
    "sugar": ("Sugar", "g"),
    "sugars": ("Sugar", "g"),
    "cukry": ("Sugar", "g"),
    "z_toho_cukry": ("Sugar", "g"),
    "salt": ("Salt", "g"),
    "sul": ("Salt", "g"),
    "water": ("Water", "ml"),
    "pitny_rezim": ("Water", "ml"),
    "voda": ("Water", "ml"),
    "weight": ("Body weight", "kg"),
}

IGNORED_SUMMARY_KEYS = {
    "code",
    "date",
    "description",
    "id",
    "monthweight",
    "name",
    "slug",
    "timestamp",
    "title",
    "unit",
    "value",
}


class KalorickeTabulkyApi:
    """Small async client for the unofficial Kaloricke Tabulky endpoints."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._cookies: str | None = None

    async def authenticate(self) -> None:
        """Authenticate and store the returned session cookies."""
        response = await self._session.post(
            LOGIN_URL,
            json={
                "email": self._email,
                "password": md5(self._password.encode(), usedforsecurity=False).hexdigest(),
            },
        )
        body = await self._json_response(response)
        if body.get("code") != 0:
            raise InvalidAuthError(body.get("message") or "Invalid credentials")

        cookies = SimpleCookie()
        for header in response.headers.getall("Set-Cookie", []):
            cookies.load(header)

        cookie_header = "; ".join(f"{key}={morsel.value}" for key, morsel in cookies.items())
        if not cookie_header:
            raise InvalidAuthError("Authentication did not return session cookies")

        self._cookies = cookie_header

    async def async_get_summary(self, target_date: date | None = None) -> SummaryData:
        """Return parsed data from the daily/monthly summary endpoint."""
        request_date = target_date or date.today()
        statistic_body = await self._request_with_reauth(
            "GET",
            SUMMARY_URL.format(date=self._format_date(request_date)),
        )
        statistic_data = statistic_body.get("data") or {}
        month_weight = statistic_data.get("monthWeight") or []
        weight_records = [
            WeightRecord(date_label=str(item["description"]), weight=float(item["value"]))
            for item in month_weight
            if item.get("value") is not None
        ]

        diary_body = await self._request_with_reauth(
            "GET",
            DIARY_SUMMARY_URL.format(date=self._format_date(request_date)),
        )
        diary_data = diary_body.get("data") or {}
        return SummaryData(
            weight_records=weight_records,
            metrics=_extract_diary_summary_metrics(diary_data),
            raw={"statistic": statistic_data, "diary": diary_data},
        )

    async def async_get_recent_weight(self, target_date: date | None = None) -> list[WeightRecord]:
        """Return recent weight records from the monthly summary endpoint."""
        return (await self.async_get_summary(target_date)).weight_records

    async def async_record_weight(
        self, weight: float, target_date: date | None = None
    ) -> dict[str, Any]:
        """Record a weight value."""
        return await self._request_with_reauth(
            "POST",
            RECORD_WEIGHT_URL,
            json={"weight": weight, "date": self._format_date(target_date or date.today())},
        )

    async def _request_with_reauth(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Run an authenticated request, refreshing cookies once if needed."""
        if self._cookies is None:
            await self.authenticate()

        try:
            return await self._request(method, url, **kwargs)
        except SessionExpiredError:
            await self.authenticate()
            return await self._request(method, url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        headers["Cookie"] = self._cookies or ""
        response = await self._session.request(
            method, url, headers=headers, allow_redirects=False, **kwargs
        )
        body = await self._json_response(response)
        if response.status in (301, 302, 303, 307, 308):
            raise SessionExpiredError("Session expired")
        if body.get("code") != 0:
            raise KalorickeTabulkyError(body.get("message") or f"Unexpected API response: {body}")
        return body

    @staticmethod
    async def _json_response(response: ClientResponse) -> dict[str, Any]:
        content_type = response.headers.get("Content-Type", "")
        if response.status in (301, 302, 303, 307, 308):
            raise SessionExpiredError("Session expired")
        if "json" not in content_type:
            text = await response.text()
            raise KalorickeTabulkyError(f"Unexpected non-JSON response: {text[:200]}")
        return await response.json()

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%d.%m.%Y")


def parse_service_date(value: str | None) -> date | None:
    """Parse a Home Assistant date selector value or Czech API date."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("Date must use YYYY-MM-DD or DD.MM.YYYY format")


def _extract_summary_metrics(data: dict[str, Any]) -> dict[str, SummaryMetric]:
    """Extract useful numeric sensors from the summary payload.

    The endpoint is unofficial and its full schema is not documented. This keeps
    known nutrition/body metrics stable while also accepting value/unit objects
    that the web API may return for additional daily totals.
    """
    metrics: dict[str, SummaryMetric] = {}
    _collect_metric_values(data, (), metrics)
    return metrics


def _extract_diary_summary_metrics(data: dict[str, Any]) -> dict[str, SummaryMetric]:
    """Extract daily summary metrics from the diary summary endpoint."""
    metrics: dict[str, SummaryMetric] = {}
    for item in _iter_diary_items(data.get("items")):
        metric = _metric_from_diary_item(item)
        if metric is not None:
            metrics.setdefault(metric.key, metric)

    for item in _iter_diary_items(data.get("itemsDynamic")):
        metric = _metric_from_diary_item(item)
        if metric is not None:
            metrics.setdefault(metric.key, metric)

    _add_diary_total_metrics(data, metrics)
    _add_balance_metrics(data.get("balance"), metrics)

    if not metrics:
        metrics = _extract_summary_metrics(data)
    return metrics


def _iter_diary_items(value: Any) -> list[dict[str, Any]]:
    """Return all diary summary item dictionaries from nested lists."""
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []

    items: list[dict[str, Any]] = []
    for item in value:
        items.extend(_iter_diary_items(item))
    return items


def _metric_from_diary_item(item: dict[str, Any]) -> SummaryMetric | None:
    value = _diary_item_value(item)
    if value is None:
        return None

    raw_name = item.get("code") or item.get("title") or item.get("titleShort")
    if not raw_name:
        return None

    key = _normalize_key(str(raw_name))
    known = KNOWN_METRICS.get(key)
    name = _clean_name(str(raw_name))
    unit = _clean_unit(item.get("unit"))
    if known is not None:
        name, default_unit = known
        unit = unit or default_unit

    percent = item.get("percent")
    return SummaryMetric(
        key=key,
        name=name,
        value=value,
        unit=unit,
        goal=_parse_localized_number(item.get("goal")),
        percent=percent if isinstance(percent, int) and not isinstance(percent, bool) else None,
    )


def _diary_item_value(item: dict[str, Any]) -> float | None:
    actual_value = _parse_localized_number(item.get("actualValue"))
    actual = _parse_localized_number(item.get("actual"))
    if actual_value not in (None, 0.0):
        return actual_value
    return actual


def _add_diary_total_metrics(
    data: dict[str, Any], metrics: dict[str, SummaryMetric]
) -> None:
    for source_key, metric_key in (("activityEnergyTotal", "activity_energy_total"),):
        value = _parse_localized_number(data.get(source_key))
        if value is not None:
            metrics.setdefault(metric_key, _known_metric(metric_key, value))

    if "cilova_hmotnost" not in metrics:
        weight = _parse_localized_number(data.get("weight"))
        if weight is not None:
            metrics.setdefault("weight", _known_metric("weight", weight))


def _add_balance_metrics(value: Any, metrics: dict[str, SummaryMetric]) -> None:
    if not isinstance(value, dict):
        return

    balance_fields = {
        "energyOutputTotal": "energy_output_total",
        "energyIntakeMaintenance": "energy_intake_maintenance",
        "energyDeficit": "energy_deficit",
        "target": "energy_target",
        "basal": "basal_metabolism",
        "intakeRest": "energy_intake_rest",
    }
    for source_key, metric_key in balance_fields.items():
        metric_value = _parse_localized_number(value.get(source_key))
        if metric_value is not None:
            metrics.setdefault(metric_key, _known_metric(metric_key, metric_value))

    aml = value.get("aml")
    if isinstance(aml, dict):
        aml_energy = _parse_localized_number(aml.get("energy"))
        if aml_energy is not None:
            metric = _known_metric("activity_level_energy", aml_energy)
            unit = _clean_unit(aml.get("energyUnit")) or metric.unit
            metrics.setdefault(
                metric.key,
                SummaryMetric(
                    key=metric.key,
                    name=metric.name,
                    value=metric.value,
                    unit=unit,
                ),
            )


def _known_metric(key: str, value: float) -> SummaryMetric:
    name, unit = KNOWN_METRICS[key]
    return SummaryMetric(key=key, name=name, value=value, unit=unit)


def _collect_metric_values(
    value: Any, path: tuple[str, ...], metrics: dict[str, SummaryMetric]
) -> None:
    if isinstance(value, dict):
        metric = _metric_from_value_object(value, path)
        if metric is not None:
            metrics.setdefault(metric.key, metric)

        for child_key, child_value in value.items():
            normalized_child_key = _normalize_key(child_key)
            if normalized_child_key in IGNORED_SUMMARY_KEYS:
                continue
            if _is_number(child_value):
                metric = _metric_from_plain_value(child_key, child_value, path)
                if metric is not None:
                    metrics.setdefault(metric.key, metric)
            elif isinstance(child_value, dict | list):
                _collect_metric_values(child_value, (*path, str(child_key)), metrics)
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, dict):
                metric = _metric_from_value_object(item, path)
                if metric is not None:
                    metrics.setdefault(metric.key, metric)
                else:
                    _collect_metric_values(item, (*path, str(index)), metrics)


def _metric_from_value_object(
    item: dict[str, Any], path: tuple[str, ...]
) -> SummaryMetric | None:
    if not _is_number(item.get("value")):
        return None

    raw_name = (
        item.get("description")
        or item.get("name")
        or item.get("title")
        or item.get("label")
        or (path[-1] if path else None)
    )
    if not raw_name:
        return None

    normalized_name = _normalize_key(str(raw_name))
    normalized_key = (
        normalized_name
        if normalized_name in KNOWN_METRICS
        else _normalize_key(_metric_key(path, str(raw_name)))
    )
    known = KNOWN_METRICS.get(normalized_key)
    unit = _clean_unit(item.get("unit") or item.get("unitName") or item.get("unit_name"))
    name = _clean_name(str(raw_name))
    if known is not None:
        name, default_unit = known
        unit = unit or default_unit

    if known is None and unit is None and normalized_key not in KNOWN_METRICS:
        return None

    return SummaryMetric(
        key=normalized_key,
        name=name,
        value=float(item["value"]),
        unit=unit,
    )


def _metric_from_plain_value(
    key: str, value: Any, path: tuple[str, ...]
) -> SummaryMetric | None:
    metric_key = _normalize_key(_metric_key(path, key))
    simple_key = _normalize_key(key)
    known = KNOWN_METRICS.get(simple_key) or KNOWN_METRICS.get(metric_key)
    if known is None:
        return None
    return SummaryMetric(
        key=simple_key if simple_key in KNOWN_METRICS else metric_key,
        name=known[0],
        value=float(value),
        unit=known[1],
    )


def _metric_key(path: tuple[str, ...], name: str) -> str:
    parts = [part for part in (*path, name) if not part.isdigit()]
    return "_".join(parts)


def _normalize_key(value: str) -> str:
    value = value.lower()
    value = value.translate(str.maketrans("áčďéěíňóřšťúůýž", "acdeeinorstuuyz"))
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().capitalize()


def _clean_unit(value: Any) -> str | None:
    if value is None:
        return None
    unit = str(value).strip()
    return unit or None


def _parse_localized_number(value: Any) -> float | None:
    if _is_number(value):
        return float(value)
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("\xa0", " ").replace(" ", "")
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
