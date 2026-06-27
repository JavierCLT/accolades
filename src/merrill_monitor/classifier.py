from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from .models import (
    ALLOWED_ACTIONS,
    ALLOWED_CATEGORIES,
    ALLOWED_SENTIMENTS,
    CandidateItem,
    ClassifiedItem,
)
from .utils import compact_whitespace, stable_id, two_sentence_summary


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Classification:
    summary: str
    category: str
    sentiment: str
    relevance_score: int
    is_accolade: bool
    is_forum_discussion: bool
    action_recommendation: str
    raw_json: dict[str, Any]


class ItemClassifier:
    def __init__(
        self,
        *,
        use_llm: bool = False,
        openai_model: str | None = None,
        openai_reasoning_effort: str | None = None,
    ) -> None:
        self.use_llm = use_llm
        self.openai_model = openai_model or os.getenv("OPENAI_MODEL")
        self.openai_reasoning_effort = (
            openai_reasoning_effort
            or os.getenv("OPENAI_REASONING_EFFORT")
            or "low"
        ).strip().lower()

    def classify(self, candidate: CandidateItem) -> ClassifiedItem:
        classification: Classification | None = None
        if self.use_llm:
            try:
                classification = self._classify_with_llm(candidate)
            except Exception:
                LOGGER.exception("LLM classification failed; falling back to rules for %s", candidate.url)

        if classification is None:
            classification = self._classify_with_rules(candidate)

        return ClassifiedItem(
            id=stable_id(candidate.source, candidate.normalized_url, candidate.title),
            source=candidate.source,
            url=candidate.url,
            normalized_url=candidate.normalized_url,
            title=candidate.title,
            snippet=candidate.snippet,
            summary=classification.summary,
            published_date=candidate.published_date,
            category=classification.category,
            sentiment=classification.sentiment,
            relevance_score=classification.relevance_score,
            is_accolade=classification.is_accolade,
            is_forum_discussion=classification.is_forum_discussion,
            action_recommendation=classification.action_recommendation,
            raw_json=classification.raw_json,
        )

    def _classify_with_llm(self, candidate: CandidateItem) -> Classification:
        if not self.openai_model:
            raise RuntimeError("OPENAI_MODEL must be set when LLM_CLASSIFIER_ENABLED=true")
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY must be set when LLM_CLASSIFIER_ENABLED=true")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install with 'pip install -e .[llm]' to use LLM classification") from exc

        client = OpenAI()
        prompt = {
            "source": candidate.source,
            "url": candidate.url,
            "title": candidate.title,
            "snippet": candidate.snippet,
            "published_date": candidate.published_date,
            "metadata": candidate.metadata,
            "allowed_categories": ALLOWED_CATEGORIES,
            "allowed_sentiments": sorted(ALLOWED_SENTIMENTS),
            "allowed_actions": sorted(ALLOWED_ACTIONS),
        }
        response = client.responses.create(
            model=self.openai_model,
            reasoning={"effort": self.openai_reasoning_effort},
            text={"format": {"type": "json_object"}},
            input=[
                {
                    "role": "system",
                    "content": (
                        "Classify Merrill Edge monitoring results for a brokerage marketing, "
                        "product, and service team. Return strict JSON with keys: summary, "
                        "category, sentiment, relevance_score, is_accolade, "
                        "is_forum_discussion, action_recommendation. Summary must be exactly "
                        "two concise sentences. relevance_score is an integer 0-100."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        )
        content = extract_response_text(response)
        payload = json.loads(content)
        return self._sanitize_classification(payload, candidate)

    def _classify_with_rules(self, candidate: CandidateItem) -> Classification:
        text = compact_whitespace(f"{candidate.title} {candidate.snippet}").lower()
        source_kind = str(candidate.metadata.get("source_kind", "")).strip().lower()
        category = "Other"
        sentiment = infer_sentiment(text)

        accolade_terms = [
            "award",
            "accolade",
            "ranked",
            "ranking",
            "best online broker",
            "best brokerage",
            "best for",
            "top broker",
            "editor's choice",
            "winner",
        ]
        competitor_terms = [
            "vs",
            "versus",
            "compare",
            "comparison",
            "fidelity",
            "schwab",
            "vanguard",
            "etrade",
            "e*trade",
            "robinhood",
            "interactive brokers",
        ]
        complaint_terms = [
            "complaint",
            "problem",
            "issue",
            "broken",
            "can't",
            "cannot",
            "unable",
            "worst",
            "terrible",
            "frustrating",
            "delay",
            "locked",
            "error",
        ]
        competitor_offer_terms = [
            "bonus",
            "promotion",
            "promo",
            "cash bonus",
            "transfer bonus",
            "new account offer",
            "deposit bonus",
            "limited time offer",
            "cash reward",
        ]
        regulatory_terms = [
            "cfpb",
            "finra",
            "sec",
            "regulatory",
            "lawsuit",
            "enforcement",
            "settlement",
            "fine",
            "consent order",
            "class action",
        ]
        cash_rate_terms = [
            "money market",
            "cash sweep",
            "cash yield",
            "settlement fund",
            "sweep rate",
            "apy",
            "interest rate",
            "brokered cd",
            "treasury yield",
        ]

        if source_kind == "apple_app_store_reviews":
            category = "Mobile app review"
            sentiment = infer_app_review_sentiment(candidate.metadata.get("rating")) or sentiment
        elif source_kind == "cfpb_complaints":
            category = "Regulatory / complaint signal"
            sentiment = "negative"
        elif source_kind == "fred_series":
            category = "Cash yield / rate change"
            sentiment = "neutral"
        elif contains_any(text, accolade_terms):
            category = "New accolade / award"
        elif contains_any(text, regulatory_terms):
            category = "Regulatory / complaint signal"
        elif contains_any(text, competitor_offer_terms):
            category = "Competitor offer / promotion"
        elif contains_any(text, cash_rate_terms) and (
            contains_any(text, competitor_terms)
            or contains_any(text, ["best brokerage", "brokerage cash sweep", "treasury yield", "federal funds"])
        ):
            category = "Cash yield / rate change"
        elif contains_any(text, ["margin rate", "margin rates", "advisory fee", "contract fee"]) and contains_any(text, competitor_terms):
            category = "Competitor pricing / fees"
        elif contains_any(text, competitor_terms):
            category = "Competitor comparison"
        elif contains_any(text, ["money market", "cash sweep", "cash yield", "settlement fund", "sweep rate", "yield"]):
            category = "Money market / cash yield discussion"
        elif contains_any(text, ["acat", "account transfer", "transfer out", "transfer delay", "rollover", "move account"]):
            category = "Account transfer / ACAT discussion"
        elif contains_any(text, ["fee", "fees", "pricing", "commission", "margin rate", "expense", "charge"]):
            category = "Fees / pricing"
        elif contains_any(text, ["app", "mobile", "website", "login", "site", "online", "platform", "dashboard"]):
            category = "App or website experience"
        elif contains_any(text, ["customer service", "support", "call center", "representative", "phone", "chat"]):
            category = "Customer service"
        elif contains_any(text, ["options", "fractional shares", "research tools", "preferred rewards", "feature"]):
            category = "Product feature discussion"
        elif contains_any(text, complaint_terms):
            category = "Customer complaint"

        is_forum_discussion = bool(candidate.metadata.get("is_forum_discussion"))
        is_accolade = category == "New accolade / award"
        relevance_score = score_relevance(
            text=text,
            category=category,
            sentiment=sentiment,
            is_accolade=is_accolade,
            is_forum_discussion=is_forum_discussion,
        )
        action = recommend_action(
            category=category,
            sentiment=sentiment,
            relevance_score=relevance_score,
            is_accolade=is_accolade,
        )
        return Classification(
            summary=two_sentence_summary(candidate.title, candidate.snippet, category),
            category=category,
            sentiment=sentiment,
            relevance_score=relevance_score,
            is_accolade=is_accolade,
            is_forum_discussion=is_forum_discussion,
            action_recommendation=action,
            raw_json={"classifier": "rules"},
        )

    def _sanitize_classification(self, payload: dict[str, Any], candidate: CandidateItem) -> Classification:
        category = payload.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = "Other"

        sentiment = str(payload.get("sentiment", "neutral")).lower()
        if sentiment not in ALLOWED_SENTIMENTS:
            sentiment = "neutral"

        action = str(payload.get("action_recommendation", "monitor")).lower()
        if action not in ALLOWED_ACTIONS:
            action = recommend_action(
                category=category,
                sentiment=sentiment,
                relevance_score=int(payload.get("relevance_score", 50) or 50),
                is_accolade=bool(payload.get("is_accolade")),
            )

        try:
            relevance_score = int(payload.get("relevance_score", 50))
        except (TypeError, ValueError):
            relevance_score = 50
        relevance_score = max(0, min(100, relevance_score))

        summary = compact_whitespace(str(payload.get("summary", "")))
        if not summary:
            summary = two_sentence_summary(candidate.title, candidate.snippet, category)
        else:
            summary = two_sentence_summary(summary, "", category)

        return Classification(
            summary=summary,
            category=category,
            sentiment=sentiment,
            relevance_score=relevance_score,
            is_accolade=bool(payload.get("is_accolade")) or category == "New accolade / award",
            is_forum_discussion=bool(payload.get("is_forum_discussion")) or bool(candidate.metadata.get("is_forum_discussion")),
            action_recommendation=action,
            raw_json={**payload, "classifier": "llm"},
        )


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    output = getattr(response, "output", None) or []
    text_parts: list[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for content_item in content:
            text = getattr(content_item, "text", None)
            if text:
                text_parts.append(str(text))
    return "\n".join(text_parts) or "{}"


def infer_sentiment(text: str) -> str:
    positive_terms = [
        "best",
        "award",
        "ranked",
        "top",
        "excellent",
        "great",
        "good",
        "recommend",
        "winner",
        "low fee",
        "no commission",
    ]
    negative_terms = [
        "complaint",
        "problem",
        "issue",
        "broken",
        "can't",
        "cannot",
        "unable",
        "worst",
        "terrible",
        "frustrating",
        "delay",
        "locked",
        "error",
        "poor",
        "bad",
    ]
    has_positive = contains_any(text, positive_terms)
    has_negative = contains_any(text, negative_terms)
    if has_positive and has_negative:
        return "mixed"
    if has_positive:
        return "positive"
    if has_negative:
        return "negative"
    return "neutral"


def infer_app_review_sentiment(rating: object) -> str | None:
    try:
        numeric_rating = float(str(rating).strip())
    except (TypeError, ValueError):
        return None
    if numeric_rating <= 2:
        return "negative"
    if numeric_rating == 3:
        return "mixed"
    return "positive"


def score_relevance(
    *,
    text: str,
    category: str,
    sentiment: str,
    is_accolade: bool,
    is_forum_discussion: bool,
) -> int:
    score = 25
    if "merrill edge" in text:
        score += 25
    elif "merrill" in text:
        score += 15
    if category != "Other":
        score += 15
    if is_accolade:
        score += 25
    if category in {"Regulatory / complaint signal", "Competitor offer / promotion"}:
        score += 25
    if category in {"Cash yield / rate change", "Competitor pricing / fees", "Mobile app review", "Competitive product gap"}:
        score += 15
    if is_forum_discussion:
        score += 10
    if sentiment in {"negative", "mixed"}:
        score += 15
    if re.search(r"\b(fidelity|schwab|vanguard|robinhood|e\*?trade)\b", text):
        score += 10
    return max(0, min(100, score))


def recommend_action(
    *,
    category: str,
    sentiment: str,
    relevance_score: int,
    is_accolade: bool,
) -> str:
    if is_accolade:
        return "add to accolades tracker"
    if category == "Regulatory / complaint signal":
        return "escalate to compliance"
    if category == "Competitor offer / promotion":
        if relevance_score >= 75:
            return "competitive threat"
        return "review competitor offer"
    if category in {"Cash yield / rate change", "Money market / cash yield discussion"}:
        if sentiment in {"negative", "mixed"} and relevance_score >= 60:
            return "escalate to product"
        return "review cash yield positioning"
    if category == "Mobile app review" and sentiment in {"negative", "mixed"}:
        return "escalate app issue"
    if category in {"Competitor pricing / fees", "Competitive product gap"} and relevance_score >= 60:
        return "competitive threat"
    if category == "Competitor comparison" and relevance_score >= 60:
        return "competitive threat"
    if sentiment in {"negative", "mixed"}:
        if category == "Customer service":
            return "escalate to service"
        if category in {
            "Product feature discussion",
            "Money market / cash yield discussion",
            "Account transfer / ACAT discussion",
            "Fees / pricing",
            "App or website experience",
            "Customer complaint",
        }:
            return "escalate to product"
    if sentiment == "positive" and relevance_score >= 75:
        return "consider using in marketing copy"
    if relevance_score >= 45:
        return "monitor"
    return "ignore"
