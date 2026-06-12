from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .models import CandidateItem
from .utils import first_nonempty, normalize_url, trim_text


LOGGER = logging.getLogger(__name__)
GOOGLE_CSE_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"


class GoogleSearchConfigurationError(RuntimeError):
    """Raised when Google rejects credentials, API access, or engine configuration."""


class GoogleCustomSearchClient:
    def __init__(
        self,
        api_key: str | None = None,
        cse_id: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_CSE_API_KEY")
        self.cse_id = cse_id or os.getenv("GOOGLE_CSE_ID")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.cse_id)

    def search(
        self,
        *,
        source_name: str,
        query_group: str,
        query: str,
        result_limit: int = 10,
        date_restrict: str | None = None,
        safe: str | None = "active",
        site_restrict: str | None = None,
        is_forum_discussion: bool = False,
    ) -> list[CandidateItem]:
        if not self.is_configured:
            LOGGER.warning("Google Custom Search is not configured; skipping %s", source_name)
            return []

        effective_query = f"site:{site_restrict} {query}" if site_restrict else query
        results: list[CandidateItem] = []
        start = 1
        remaining = max(0, result_limit)

        while remaining > 0:
            page_size = min(10, remaining)
            params: dict[str, Any] = {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": effective_query,
                "num": page_size,
                "start": start,
            }
            if date_restrict:
                params["dateRestrict"] = date_restrict
            if safe:
                params["safe"] = safe

            try:
                response = self.session.get(
                    GOOGLE_CSE_ENDPOINT,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                if response.status_code in {401, 403}:
                    raise GoogleSearchConfigurationError(
                        format_google_error(response, effective_query)
                    )
                response.raise_for_status()
                payload = response.json()
            except GoogleSearchConfigurationError:
                raise
            except requests.RequestException:
                LOGGER.exception("Google Custom Search request failed for query=%r", effective_query)
                break
            except ValueError:
                LOGGER.exception("Google Custom Search returned invalid JSON for query=%r", effective_query)
                break

            items = payload.get("items", []) or []
            for item in items:
                candidate = self._to_candidate(
                    source_name=source_name,
                    query_group=query_group,
                    query=effective_query,
                    item=item,
                    is_forum_discussion=is_forum_discussion,
                )
                if candidate:
                    results.append(candidate)

            if len(items) < page_size:
                break
            remaining -= page_size
            start += page_size

        return results

    def _to_candidate(
        self,
        *,
        source_name: str,
        query_group: str,
        query: str,
        item: dict[str, Any],
        is_forum_discussion: bool,
    ) -> CandidateItem | None:
        url = item.get("link") or item.get("formattedUrl")
        if not url:
            return None
        title = trim_text(item.get("title", ""), 240)
        snippet = trim_text(item.get("snippet", ""), 500)
        normalized_url = normalize_url(url)
        published_date = extract_published_date(item)
        return CandidateItem(
            source=source_name,
            url=url,
            normalized_url=normalized_url,
            title=title,
            snippet=snippet,
            published_date=published_date,
            metadata={
                "source_kind": "google_cse",
                "query_group": query_group,
                "query": query,
                "is_forum_discussion": is_forum_discussion,
            },
        )


def format_google_error(response: requests.Response, query: str) -> str:
    reason = ""
    message = response.text.strip()
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if isinstance(payload, dict):
        error = payload.get("error", {})
        if isinstance(error, dict):
            message = str(error.get("message") or message)
            errors = error.get("errors") or []
            if errors and isinstance(errors[0], dict):
                reason = str(errors[0].get("reason") or "")

    detail = f"Google Custom Search API returned {response.status_code}"
    if reason:
        detail += f" ({reason})"
    detail += f" for query={query!r}: {message}"
    return detail


def extract_published_date(item: dict[str, Any]) -> str | None:
    pagemap = item.get("pagemap", {}) if isinstance(item.get("pagemap"), dict) else {}
    metatags = pagemap.get("metatags", [])
    if not metatags:
        return None
    first_meta = metatags[0] if isinstance(metatags[0], dict) else {}
    return first_nonempty(
        [
            first_meta.get("article:published_time"),
            first_meta.get("article:modified_time"),
            first_meta.get("datepublished"),
            first_meta.get("date"),
            first_meta.get("og:updated_time"),
            first_meta.get("pubdate"),
        ]
    )
