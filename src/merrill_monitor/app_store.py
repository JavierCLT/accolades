from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from .models import CandidateItem
from .utils import normalize_url, trim_text


LOGGER = logging.getLogger(__name__)
ITUNES_REVIEWS_ENDPOINT = "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortby=mostrecent/json"


class AppStoreReviewsClient:
    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def fetch_reviews(
        self,
        *,
        source_name: str,
        app_id: str,
        app_name: str,
        country: str = "us",
        result_limit: int = 50,
    ) -> list[CandidateItem]:
        url = ITUNES_REVIEWS_ENDPOINT.format(country=country.lower(), app_id=app_id)
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            LOGGER.exception("App Store review feed request failed for app_id=%s", app_id)
            return []
        except ValueError:
            LOGGER.exception("App Store review feed returned invalid JSON for app_id=%s", app_id)
            return []

        entries = extract_review_entries(payload)
        candidates: list[CandidateItem] = []
        for entry in entries[: max(0, result_limit)]:
            candidate = self._to_candidate(
                source_name=source_name,
                country=country,
                app_id=app_id,
                app_name=app_name,
                entry=entry,
            )
            if candidate:
                candidates.append(candidate)
        return candidates

    def _to_candidate(
        self,
        *,
        source_name: str,
        country: str,
        app_id: str,
        app_name: str,
        entry: dict[str, Any],
    ) -> CandidateItem | None:
        review_id = nested_label(entry, "id")
        if not review_id:
            return None

        rating_text = nested_label(entry, "im:rating") or "unknown"
        version = nested_label(entry, "im:version")
        review_title = nested_label(entry, "title") or "Untitled review"
        review_content = nested_label(entry, "content") or ""
        updated = nested_label(entry, "updated")
        author = nested_label(entry, "author", "name")
        review_url = (
            first_review_link(entry)
            or f"https://apps.apple.com/{country.lower()}/app/id{app_id}?see-all=reviews"
        )
        normalized = normalize_url(add_query_param(review_url, "reviewId", review_id))

        title = trim_text(f"{app_name} App Store review ({rating_text} stars): {review_title}", 240)
        snippet_parts = [
            f"Rating: {rating_text}",
            f"Version: {version}" if version else "",
            f"Author: {author}" if author else "",
            review_content,
        ]
        snippet = trim_text(". ".join(part for part in snippet_parts if part), 700)

        return CandidateItem(
            source=source_name,
            url=review_url,
            normalized_url=normalized,
            title=title,
            snippet=snippet,
            published_date=updated,
            metadata={
                "source_kind": "apple_app_store_reviews",
                "app_id": app_id,
                "app_name": app_name,
                "country": country.lower(),
                "rating": rating_text,
                "version": version,
                "is_forum_discussion": True,
            },
        )


def extract_review_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    feed = payload.get("feed") if isinstance(payload, dict) else {}
    if not isinstance(feed, dict):
        return []
    entries = feed.get("entry") or []
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict) and nested_label(entry, "im:rating")]


def nested_label(payload: dict[str, Any], *keys: str) -> str | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, dict):
        value = current.get("label")
        return trim_text(str(value), 500) if value is not None else None
    if current is None:
        return None
    return trim_text(str(current), 500)


def first_review_link(entry: dict[str, Any]) -> str | None:
    links = entry.get("link")
    if isinstance(links, dict):
        links = [links]
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        attrs = link.get("attributes")
        if isinstance(attrs, dict) and attrs.get("href"):
            return str(attrs["href"])
    return None


def add_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=False)
    query_pairs.append((key, value))
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
