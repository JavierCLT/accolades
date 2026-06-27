from merrill_monitor.classifier import ItemClassifier
from merrill_monitor.models import CandidateItem
from merrill_monitor.utils import normalize_url


def make_candidate(title: str, snippet: str) -> CandidateItem:
    url = "https://example.com/article?utm_source=newsletter"
    return CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title=title,
        snippet=snippet,
        metadata={"is_forum_discussion": False},
    )


def make_candidate_with_metadata(title: str, snippet: str, metadata: dict) -> CandidateItem:
    url = "https://example.com/article?utm_source=newsletter"
    return CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title=title,
        snippet=snippet,
        metadata=metadata,
    )


def test_rule_classifier_flags_accolades() -> None:
    item = ItemClassifier(use_llm=False).classify(
        make_candidate(
            "Merrill Edge ranked best online broker",
            "A new ranking names Merrill Edge among the top brokerages.",
        )
    )
    assert item.category == "New accolade / award"
    assert item.is_accolade is True
    assert item.action_recommendation == "add to accolades tracker"
    assert item.relevance_label == "high"


def test_rule_classifier_flags_cash_yield_discussion() -> None:
    item = ItemClassifier(use_llm=False).classify(
        make_candidate(
            "Merrill Edge cash sweep rate question",
            "Customers are discussing money market yield options.",
        )
    )
    assert item.category == "Money market / cash yield discussion"
    assert item.relevance_score >= 45


def test_rule_classifier_flags_competitor_offer() -> None:
    item = ItemClassifier(use_llm=False).classify(
        make_candidate(
            "Fidelity launches brokerage bonus",
            "New account offer includes a transfer bonus for funded brokerage accounts.",
        )
    )
    assert item.category == "Competitor offer / promotion"
    assert item.action_recommendation in {"review competitor offer", "competitive threat"}


def test_rule_classifier_flags_app_store_review_from_metadata() -> None:
    item = ItemClassifier(use_llm=False).classify(
        make_candidate_with_metadata(
            "Merrill Edge App Store review (1 stars): Login problem",
            "The app will not let me sign in.",
            {"source_kind": "apple_app_store_reviews", "rating": "1", "is_forum_discussion": True},
        )
    )
    assert item.category == "Mobile app review"
    assert item.sentiment == "negative"
    assert item.action_recommendation == "escalate app issue"


def test_rule_classifier_flags_cfpb_from_metadata() -> None:
    item = ItemClassifier(use_llm=False).classify(
        make_candidate_with_metadata(
            "CFPB complaint: MERRILL EDGE - Investment account",
            "Trouble transferring account.",
            {"source_kind": "cfpb_complaints", "is_forum_discussion": True},
        )
    )
    assert item.category == "Regulatory / complaint signal"
    assert item.action_recommendation == "escalate to compliance"


def test_rule_classifier_flags_fred_from_metadata() -> None:
    item = ItemClassifier(use_llm=False).classify(
        make_candidate_with_metadata(
            "FRED rate watch: Effective Federal Funds Rate is 4.33",
            "Use this as market-rate context for brokerage yield positioning.",
            {"source_kind": "fred_series", "is_forum_discussion": False},
        )
    )
    assert item.category == "Cash yield / rate change"
    assert item.action_recommendation == "review cash yield positioning"
