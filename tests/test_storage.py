from merrill_monitor.classifier import ItemClassifier
from merrill_monitor.models import CandidateItem
from merrill_monitor.storage import SeenStore
from merrill_monitor.utils import normalize_url


def test_storage_dedupes_by_normalized_url(tmp_path) -> None:
    db_path = tmp_path / "monitor.sqlite"
    store = SeenStore(db_path)
    url = "https://example.com/post?utm_campaign=test&id=123"
    candidate = CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title="Merrill Edge review",
        snippet="A review mentions Merrill Edge.",
    )
    item = ItemClassifier(use_llm=False).classify(candidate)

    assert store.insert_new(item, "2026-06-06") is True
    assert store.insert_new(item, "2026-06-06") is False
    assert store.count() == 1
