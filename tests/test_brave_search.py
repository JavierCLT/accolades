from __future__ import annotations

import json

import requests

from merrill_monitor.brave_search import extract_web_results, format_brave_error


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
