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
