from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .models import CandidateItem
from .utils import first_nonempty, normalize_url, trim_text


LOGGER = logging.getLogger(__name__)
CFPB_COMPLAINT_SEARCH_ENDPOINT = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"


class CFPBComplaintsClient:
    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def search_complaints(
        self,
        *,
        source_name: str,
        companies: list[str] | None = None,
        search_terms: list[str] | None = None,
        date_window_days: int = 30,
        result_limit: int = 25,
    ) -> list[CandidateItem]:
        date_received_min = (
            datetime.now(timezone.utc).date() - timedelta(days=max(1, date_window_days))
        ).isoformat()
        requests_to_make: list[dict[str, str]] = []

        for company in companies or []:
            if company.strip():
                requests_to_make.append({"company": company.strip()})
        for term in search_terms or []:
            if term.strip():
                requests_to_make.append({"search_term": term.strip()})
        if not requests_to_make:
            requests_to_make.append({})

        candidates: list[CandidateItem] = []
        for request_params in requests_to_make:
            candidates.extend(
                self._search_once(
                    source_name=source_name,
                    date_received_min=date_received_min,
                    result_limit=result_limit,
                    extra_params=request_params,
                )
            )
        return candidates

    def _search_once(
        self,
        *,
        source_name: str,
        date_received_min: str,
        result_limit: int,
        extra_params: dict[str, str],
    ) -> list[CandidateItem]:
        params: dict[str, Any] = {
            "format": "json",
            "size": max(1, min(result_limit, 100)),
            "sort": "created_date_desc",
            "date_received_min": date_received_min,
            **extra_params,
        }
        try:
            response = self.session.get(
                CFPB_COMPLAINT_SEARCH_ENDPOINT,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            LOGGER.exception("CFPB complaint API request failed with params=%s", extra_params)
            return []
        except ValueError:
            LOGGER.exception("CFPB complaint API returned invalid JSON with params=%s", extra_params)
            return []

        records = extract_complaint_records(payload)
        candidates: list[CandidateItem] = []
        for record in records[: max(0, result_limit)]:
            candidate = self._to_candidate(source_name=source_name, record=record)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _to_candidate(self, *, source_name: str, record: dict[str, Any]) -> CandidateItem | None:
        complaint_id = first_nonempty(
            [
                as_text(record.get("complaint_id")),
                as_text(record.get("complaint_what_happened_id")),
                as_text(record.get("_id")),
                as_text(record.get("id")),
            ]
        )
        if not complaint_id:
            complaint_id = hashlib.sha256(repr(sorted(record.items())).encode("utf-8")).hexdigest()[:16]

        company = as_text(record.get("company")) or "Unknown company"
        product = as_text(record.get("product")) or "Unknown product"
        issue = as_text(record.get("issue")) or "Unknown issue"
        sub_issue = as_text(record.get("sub_issue"))
        narrative = as_text(record.get("complaint_what_happened"))
        response = as_text(record.get("company_response"))
        date_received = first_nonempty([as_text(record.get("date_received")), as_text(record.get("created_date"))])

        url = f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/detail/{complaint_id}"
        title = trim_text(f"CFPB complaint: {company} - {product} - {issue}", 240)
        snippet = trim_text(
            ". ".join(
                part
                for part in [
                    f"Sub-issue: {sub_issue}" if sub_issue else "",
                    narrative or "",
                    f"Company response: {response}" if response else "",
                ]
                if part
            ),
            700,
        )
        if not snippet:
            snippet = trim_text(f"Complaint record for {company}. Product: {product}. Issue: {issue}.", 700)

        return CandidateItem(
            source=source_name,
            url=url,
            normalized_url=normalize_url(url),
            title=title,
            snippet=snippet,
            published_date=date_received,
            metadata={
                "source_kind": "cfpb_complaints",
                "complaint_id": complaint_id,
                "company": company,
                "product": product,
                "issue": issue,
                "is_forum_discussion": True,
            },
        )


def extract_complaint_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    value = payload.get("value")
    if isinstance(value, list):
        return [normalize_record(record) for record in value if isinstance(record, dict)]

    hits = payload.get("hits")
    if isinstance(hits, dict):
        hit_records = hits.get("hits") or []
        if isinstance(hit_records, list):
            return [normalize_record(record) for record in hit_records if isinstance(record, dict)]
    if isinstance(hits, list):
        return [normalize_record(record) for record in hits if isinstance(record, dict)]

    return []


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("_source")
    if isinstance(source, dict):
        return {**source, **{key: value for key, value in record.items() if key != "_source"}}
    return record


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)
