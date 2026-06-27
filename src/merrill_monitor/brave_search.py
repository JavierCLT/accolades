from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .models import CandidateItem
from .utils import first_nonempty, normalize_url, normalize_url_with_content_signature, trim_text


LOGGER = logging.getLogger(__name__)
BRAVE_WEB_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchConfigurationError(RuntimeError):
    """Raised when Brave rejects credentials or request configuration."""


class BraveSearchClient:
    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(
        self,
        *,
        source_name: str,
        query_group: str,
        query: str,
        result_limit: int = 10,
        freshness: str | None = None,
        safesearch: str | None = "moderate",
        country: str | None = "US",
        search_lang: str | None = "en",
        site_restrict: str | None = None,
        is_forum_discussion: bool = False,
        dedupe_strategy: str = "url",
    ) -> list[CandidateItem]:
        if not self.is_configured:
            LOGGER.warning("Brave Search is not configured; skipping %s", source_name)
            return []

        effective_query = f"site:{site_restrict} {query}" if site_restrict else query
        results: list[CandidateItem] = []
        remaining = max(0, result_limit)
        offset = 0

        while remaining > 0 and offset <= 9:
            count = min(20, remaining)
            params: dict[str, Any] = {
                "q": effective_query,
                "count": count,
                "offset": offset,
                "result_filter": "web",
                "text_decorations": "false",
            }
            if freshness:
                params["freshness"] = freshness
            if safesearch:
                params["safesearch"] = safesearch
            if country:
                params["country"] = country
            if search_lang:
                params["search_lang"] = search_lang

            try:
                response = self.session.get(
                    BRAVE_WEB_SEARCH_ENDPOINT,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self.api_key,
                    },
                    params=params,
                    timeout=self.timeout_seconds,
                )
                if response.status_code in {401, 403, 422, 429}:
                    raise BraveSearchConfigurationError(
                        format_brave_error(response, effective_query)
                    )
                response.raise_for_status()
                payload = response.json()
            except BraveSearchConfigurationError:
                raise
            except requests.RequestException:
                LOGGER.exception("Brave Search request failed for query=%r", effective_query)
                break
            except ValueError:
                LOGGER.exception("Brave Search returned invalid JSON for query=%r", effective_query)
                break

            items = extract_web_results(payload)
            for item in items:
                candidate = self._to_candidate(
                    source_name=source_name,
                    query_group=query_group,
                    query=effective_query,
                    item=item,
                    is_forum_discussion=is_forum_discussion,
                    dedupe_strategy=dedupe_strategy,
                )
                if candidate:
                    results.append(candidate)

            if len(items) < count:
                break
            remaining -= count
            offset += 1

        return results

    def _to_candidate(
        self,
        *,
        source_name: str,
        query_group: str,
        query: str,
        item: dict[str, Any],
        is_forum_discussion: bool,
        dedupe_strategy: str,
    ) -> CandidateItem | None:
        url = item.get("url")
        if not url:
            return None
        title = trim_text(item.get("title", ""), 240)
        snippet = trim_text(
            first_nonempty(
                [
                    item.get("description"),
                    " ".join(item.get("extra_snippets", []) or []),
                ]
            )
            or "",
            500,
        )
        normalized_url = normalize_url(url)
        if dedupe_strategy == "url_content":
            normalized_url = normalize_url_with_content_signature(url, title, snippet)

        return CandidateItem(
            source=source_name,
            url=url,
            normalized_url=normalized_url,
            title=title,
            snippet=snippet,
            published_date=first_nonempty([item.get("age"), item.get("page_age")]),
            metadata={
                "source_kind": "brave_search",
                "query_group": query_group,
                "query": query,
                "is_forum_discussion": is_forum_discussion,
                "dedupe_strategy": dedupe_strategy,
            },
        )


def extract_web_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    web = payload.get("web") if isinstance(payload, dict) else {}
    if not isinstance(web, dict):
        return []
    results = web.get("results") or []
    return [item for item in results if isinstance(item, dict)]


def format_brave_error(response: requests.Response, query: str) -> str:
    message = response.text.strip()
    error_code = ""
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if isinstance(payload, dict):
        error = payload.get("error", {})
        if isinstance(error, dict):
            message = str(error.get("detail") or error.get("message") or message)
            error_code = str(error.get("code") or "")
        elif payload.get("message"):
            message = str(payload["message"])

    detail = f"Brave Search API returned {response.status_code}"
    if error_code:
        detail += f" ({error_code})"
    detail += f" for query={query!r}: {message}"
    return detail
