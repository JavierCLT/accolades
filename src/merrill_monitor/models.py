from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_CATEGORIES = [
    "New accolade / award",
    "Competitor comparison",
    "Customer complaint",
    "Product feature discussion",
    "Money market / cash yield discussion",
    "Account transfer / ACAT discussion",
    "Fees / pricing",
    "App or website experience",
    "Customer service",
    "Other",
]

ALLOWED_SENTIMENTS = {"positive", "neutral", "negative", "mixed"}

ALLOWED_ACTIONS = {
    "ignore",
    "monitor",
    "add to accolades tracker",
    "consider using in marketing copy",
    "escalate to product",
    "escalate to service",
    "competitive threat",
}


@dataclass(frozen=True)
class CandidateItem:
    source: str
    url: str
    normalized_url: str
    title: str
    snippet: str
    published_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassifiedItem:
    id: str
    source: str
    url: str
    normalized_url: str
    title: str
    snippet: str
    summary: str
    published_date: str | None
    category: str
    sentiment: str
    relevance_score: int
    is_accolade: bool
    is_forum_discussion: bool
    action_recommendation: str
    raw_json: dict[str, Any] = field(default_factory=dict)

    @property
    def relevance_label(self) -> str:
        if self.relevance_score >= 75:
            return "high"
        if self.relevance_score >= 45:
            return "medium"
        return "low"
