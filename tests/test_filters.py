from merrill_monitor.filters import is_merrill_related_candidate
from merrill_monitor.models import CandidateItem
from merrill_monitor.utils import normalize_url


def make_candidate(title: str, snippet: str = "", metadata: dict | None = None) -> CandidateItem:
    url = "https://example.com/result"
    return CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title=title,
        snippet=snippet,
        metadata=metadata or {},
    )


def test_merrill_related_candidate_matches_merrill_edge_text() -> None:
    candidate = make_candidate("Merrill Edge ranked best brokerage")

    assert is_merrill_related_candidate(candidate) is True


def test_merrill_related_candidate_rejects_competitor_only_award() -> None:
    candidate = make_candidate("Fidelity ranked best brokerage")

    assert is_merrill_related_candidate(candidate) is False


def test_merrill_related_candidate_allows_merrill_edge_app_store_reviews() -> None:
    candidate = make_candidate(
        "Great app",
        metadata={
            "source_kind": "apple_app_store_reviews",
            "app_id": "420496625",
            "app_name": "Merrill Edge",
        },
    )

    assert is_merrill_related_candidate(candidate) is True


def test_merrill_related_candidate_rejects_non_edge_app_store_reviews() -> None:
    candidate = make_candidate(
        "Great app",
        metadata={
            "source_kind": "apple_app_store_reviews",
            "app_id": "1419745724",
            "app_name": "Benefits OnLine",
        },
    )

    assert is_merrill_related_candidate(candidate) is False
