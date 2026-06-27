from merrill_monitor.app_store import AppStoreReviewsClient, extract_review_entries


def test_extract_review_entries_filters_non_reviews() -> None:
    payload = {
        "feed": {
            "entry": [
                {"title": {"label": "Metadata"}},
                {
                    "id": {"label": "review-1"},
                    "im:rating": {"label": "2"},
                    "title": {"label": "Login problem"},
                    "content": {"label": "The app will not let me sign in."},
                },
            ]
        }
    }

    entries = extract_review_entries(payload)

    assert len(entries) == 1
    assert entries[0]["id"]["label"] == "review-1"


def test_app_store_candidate_uses_review_id_for_dedupe() -> None:
    client = AppStoreReviewsClient()
    candidate = client._to_candidate(
        source_name="apple_merrill_reviews",
        country="us",
        app_id="420496625",
        app_name="Merrill Edge",
        entry={
            "id": {"label": "14224922175"},
            "updated": {"label": "2026-06-10T12:00:00-07:00"},
            "im:rating": {"label": "1"},
            "im:version": {"label": "9.0"},
            "title": {"label": "Unable to login"},
            "content": {"label": "The app shows an error when I try to login."},
            "link": {"attributes": {"href": "https://apps.apple.com/us/app/id420496625?uo=2"}},
        },
    )

    assert candidate is not None
    assert candidate.metadata["source_kind"] == "apple_app_store_reviews"
    assert candidate.metadata["rating"] == "1"
    assert "reviewId=14224922175" in candidate.normalized_url
