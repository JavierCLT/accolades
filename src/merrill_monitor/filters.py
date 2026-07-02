from __future__ import annotations

import re
from typing import Any

from .models import CandidateItem
from .utils import compact_whitespace


MERRILL_EDGE_APP_IDS = {"420496625"}
MERRILL_RELATED_PATTERN = re.compile(
    r"\b(merrill\s+edge|merrill\s+lynch|merrill|merrill\s+self-directed|self-directed\s+investing)\b",
    re.IGNORECASE,
)


def is_merrill_related_candidate(candidate: CandidateItem) -> bool:
    source_kind = str(candidate.metadata.get("source_kind", "")).strip().lower()
    if source_kind == "apple_app_store_reviews":
        app_id = str(candidate.metadata.get("app_id", "")).strip()
        app_name = str(candidate.metadata.get("app_name", "")).strip()
        return app_id in MERRILL_EDGE_APP_IDS or bool(MERRILL_RELATED_PATTERN.search(app_name))

    return bool(MERRILL_RELATED_PATTERN.search(candidate_search_text(candidate)))


def candidate_search_text(candidate: CandidateItem) -> str:
    metadata_values = " ".join(flatten_metadata_values(candidate.metadata))
    return compact_whitespace(
        " ".join(
            [
                candidate.source,
                candidate.url,
                candidate.title,
                candidate.snippet,
                metadata_values,
            ]
        )
    )


def flatten_metadata_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        values: list[str] = []
        for child in value.values():
            values.extend(flatten_metadata_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(flatten_metadata_values(child))
        return values
    return [str(value)]
