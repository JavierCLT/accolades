from __future__ import annotations

import sys
import types

from merrill_monitor.classifier import ItemClassifier
from merrill_monitor.models import CandidateItem
from merrill_monitor.utils import normalize_url


class FakeResponses:
    last_kwargs = None

    def create(self, **kwargs):
        FakeResponses.last_kwargs = kwargs
        return types.SimpleNamespace(
            output_text=(
                '{"summary":"Merrill Edge received a new accolade. '
                'The item may be useful for marketing review.",'
                '"category":"New accolade / award",'
                '"sentiment":"positive",'
                '"relevance_score":90,'
                '"is_accolade":true,'
                '"is_forum_discussion":false,'
                '"action_recommendation":"add to accolades tracker"}'
            )
        )


class FakeOpenAI:
    def __init__(self):
        self.responses = FakeResponses()


def test_llm_classifier_uses_low_reasoning(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    url = "https://example.com/merrill-edge-award"
    candidate = CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title="Merrill Edge wins award",
        snippet="A ranking recognized Merrill Edge.",
        metadata={"is_forum_discussion": False},
    )

    item = ItemClassifier(
        use_llm=True,
        openai_model="gpt-5.5",
        openai_reasoning_effort="low",
    ).classify(candidate)

    assert item.category == "New accolade / award"
    assert FakeResponses.last_kwargs["model"] == "gpt-5.5"
    assert FakeResponses.last_kwargs["reasoning"] == {"effort": "low"}
