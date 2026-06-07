from merrill_monitor.utils import normalize_url, two_sentence_summary


def test_normalize_url_removes_tracking_and_www() -> None:
    assert (
        normalize_url("https://www.Example.com/path/?utm_source=x&b=2&a=1#section")
        == "https://example.com/path?a=1&b=2"
    )


def test_two_sentence_summary_returns_two_sentences() -> None:
    summary = two_sentence_summary("Merrill Edge review", "Customers compare cash yield.", "Other")
    assert len([part for part in summary.split(".") if part.strip()]) == 2
