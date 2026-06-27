from __future__ import annotations

import json

import requests

from merrill_monitor.brave_search import BraveSearchClient, extract_web_results, format_brave_error


def test_extract_web_results() -> None:
    payload = {
        "web": {
            "results": [
                {"title": "Merrill Edge review", "url": "https://example.com/a"},
                "ignored",
            ]
        }
    }

    assert extract_web_results(payload) == [
        {"title": "Merrill Edge review", "url": "https://example.com/a"}
    ]


def test_format_brave_error_includes_status_and_message() -> None:
    response = requests.Response()
    response.status_code = 401
    response._content = json.dumps(
        {"error": {"code": "unauthorized", "detail": "Invalid API key"}}
    ).encode("utf-8")

    message = format_brave_error(response, '"Merrill Edge" award')

    assert "401" in message
    assert "unauthorized" in message
    assert "Invalid API key" in message


def test_brave_url_content_dedupe_uses_result_text_signature() -> None:
    client = BraveSearchClient(api_key="test-key")

    first = client._to_candidate(
        source_name="test",
        query_group="offers",
        query='"Fidelity" bonus',
        item={"title": "Brokerage bonus", "url": "https://example.com/bonus", "description": "Get $500."},
        is_forum_discussion=False,
        dedupe_strategy="url_content",
    )
    second = client._to_candidate(
        source_name="test",
        query_group="offers",
        query='"Fidelity" bonus',
        item={"title": "Brokerage bonus", "url": "https://example.com/bonus", "description": "Get $1000."},
        is_forum_discussion=False,
        dedupe_strategy="url_content",
    )

    assert first is not None
    assert second is not None
    assert first.url == second.url
    assert first.normalized_url != second.normalized_url
