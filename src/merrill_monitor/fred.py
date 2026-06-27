from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .models import CandidateItem
from .utils import first_nonempty, normalize_url_with_content_signature, trim_text


LOGGER = logging.getLogger(__name__)
FRED_SERIES_OBSERVATIONS_ENDPOINT = "https://api.stlouisfed.org/fred/series/observations"


class FredClient:
    def __init__(self, api_key: str | None = None, timeout_seconds: int = 20) -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def latest_observations(
        self,
        *,
        source_name: str,
        series: list[dict[str, Any]],
    ) -> list[CandidateItem]:
        if not self.is_configured:
            LOGGER.warning("FRED API is not configured; skipping source=%s", source_name)
            return []

        candidates: list[CandidateItem] = []
        for series_config in series:
            series_id = str(series_config.get("id", "")).strip()
            if not series_id:
                continue
            label = str(series_config.get("label") or series_id).strip()
            candidate = self._latest_observation(source_name=source_name, series_id=series_id, label=label)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _latest_observation(self, *, source_name: str, series_id: str, label: str) -> CandidateItem | None:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        try:
            response = self.session.get(
                FRED_SERIES_OBSERVATIONS_ENDPOINT,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            LOGGER.exception("FRED API request failed for series_id=%s", series_id)
            return None
        except ValueError:
            LOGGER.exception("FRED API returned invalid JSON for series_id=%s", series_id)
            return None

        observations = payload.get("observations") if isinstance(payload, dict) else []
        if not isinstance(observations, list) or not observations:
            LOGGER.warning("FRED API returned no observations for series_id=%s", series_id)
            return None

        observation = next((item for item in observations if isinstance(item, dict)), None)
        if not observation:
            return None

        date = first_nonempty([as_text(observation.get("date"))]) or "unknown date"
        value = first_nonempty([as_text(observation.get("value"))]) or "unknown value"
        fred_url = f"https://fred.stlouisfed.org/series/{series_id}"
        title = trim_text(f"FRED rate watch: {label} is {value} on {date}", 240)
        snippet = trim_text(
            f"Latest FRED observation for {label} ({series_id}) is {value} on {date}. "
            "Use this as market-rate context for cash sweep, money market, and brokerage yield positioning.",
            700,
        )

        return CandidateItem(
            source=source_name,
            url=fred_url,
            normalized_url=normalize_url_with_content_signature(fred_url, series_id, date, value),
            title=title,
            snippet=snippet,
            published_date=date,
            metadata={
                "source_kind": "fred_series",
                "series_id": series_id,
                "label": label,
                "value": value,
                "date": date,
                "is_forum_discussion": False,
            },
        )


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
