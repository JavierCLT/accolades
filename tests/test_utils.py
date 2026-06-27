from merrill_monitor.utils import normalize_url, normalize_url_with_content_signature, two_sentence_summary


def test_normalize_url_removes_tracking_and_www() -> None:
    assert (
        normalize_url("https://www.Example.com/path/?utm_source=x&b=2&a=1#section")
        == "https://example.com/path?a=1&b=2"
    )


def test_two_sentence_summary_returns_two_sentences() -> None:
    summary = two_sentence_summary("Merrill Edge review", "Customers compare cash yield.", "Other")
    assert len([part for part in summary.split(".") if part.strip()]) == 2


def test_content_signature_changes_normalized_url_when_content_changes() -> None:
    url = "https://www.example.com/page?utm_source=x"

    first = normalize_url_with_content_signature(url, "Offer is 500")
    second = normalize_url_with_content_signature(url, "Offer is 1000")

    assert first != second
    assert "monitor_sig=" in first
    assert first.startswith("https://example.com/page?")
