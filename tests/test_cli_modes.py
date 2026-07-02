from __future__ import annotations

from types import SimpleNamespace

from merrill_monitor import cli
from merrill_monitor.models import CandidateItem
from merrill_monitor.storage import SeenStore
from merrill_monitor.utils import normalize_url


def make_runtime(db_path):
    return SimpleNamespace(
        db_path=db_path,
        local_timezone="America/New_York",
        llm_classifier_enabled=False,
        openai_model=None,
        openai_reasoning_effort="low",
        max_items_per_digest=30,
        send_empty_digest=False,
        email_from="",
        email_to=[],
        email_backend="smtp",
    )


def make_args(sources_path, queries_path, *, dry_run=False, baseline=False):
    return SimpleNamespace(
        sources=str(sources_path),
        queries=str(queries_path),
        dry_run=dry_run,
        baseline=baseline,
        send_empty=False,
    )


def make_candidate() -> CandidateItem:
    url = "https://example.com/merrill-edge-award"
    return CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title="Merrill Edge wins award",
        snippet="A ranking recognized Merrill Edge.",
    )


def make_competitor_only_candidate() -> CandidateItem:
    url = "https://example.com/fidelity-award"
    return CandidateItem(
        source="test",
        url=url,
        normalized_url=normalize_url(url),
        title="Fidelity wins best brokerage award",
        snippet="A ranking recognized Fidelity.",
    )


def write_configs(tmp_path):
    sources_path = tmp_path / "sources.yaml"
    queries_path = tmp_path / "queries.yaml"
    sources_path.write_text("sources: []\n", encoding="utf-8")
    queries_path.write_text("query_groups: {}\n", encoding="utf-8")
    return sources_path, queries_path


def test_dry_run_does_not_write_sqlite(tmp_path, monkeypatch) -> None:
    sources_path, queries_path = write_configs(tmp_path)
    monkeypatch.setattr(cli, "collect_candidates", lambda sources, queries: [make_candidate()])

    result = cli.run_monitor(
        make_args(sources_path, queries_path, dry_run=True),
        make_runtime(tmp_path / "monitor.sqlite"),
    )

    assert result == 0
    assert SeenStore(tmp_path / "monitor.sqlite").count() == 0


def test_baseline_writes_sqlite_without_email(tmp_path, monkeypatch) -> None:
    sources_path, queries_path = write_configs(tmp_path)
    monkeypatch.setattr(cli, "collect_candidates", lambda sources, queries: [make_candidate()])

    result = cli.run_monitor(
        make_args(sources_path, queries_path, baseline=True),
        make_runtime(tmp_path / "monitor.sqlite"),
    )

    assert result == 0
    assert SeenStore(tmp_path / "monitor.sqlite").count() == 1


def test_baseline_filters_unrelated_candidates_before_storage(tmp_path, monkeypatch) -> None:
    sources_path, queries_path = write_configs(tmp_path)
    monkeypatch.setattr(cli, "collect_candidates", lambda sources, queries: [make_candidate(), make_competitor_only_candidate()])

    result = cli.run_monitor(
        make_args(sources_path, queries_path, baseline=True),
        make_runtime(tmp_path / "monitor.sqlite"),
    )

    assert result == 0
    assert SeenStore(tmp_path / "monitor.sqlite").count() == 1
