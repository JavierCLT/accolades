from __future__ import annotations

import json

import requests

from merrill_monitor.google_search import format_google_error


def test_format_google_error_includes_reason_and_message() -> None:
    response = requests.Response()
    response.status_code = 403
    response._content = json.dumps(
        {
            "error": {
                "message": "Custom Search API has not been used in project before or it is disabled.",
                "errors": [{"reason": "accessNotConfigured"}],
            }
        }
    ).encode("utf-8")

    message = format_google_error(response, '"Merrill Edge" award')

    assert "403" in message
    assert "accessNotConfigured" in message
    assert "disabled" in message
