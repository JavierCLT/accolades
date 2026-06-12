from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .utils import coerce_bool


@dataclass(frozen=True)
class RuntimeConfig:
    db_path: Path
    email_backend: str
    email_from: str
    email_to: list[str]
    send_empty_digest: bool
    max_items_per_digest: int
    local_timezone: str
    llm_classifier_enabled: bool
    openai_model: str | None
    openai_reasoning_effort: str


def load_runtime_config(db_path: str | None = None) -> RuntimeConfig:
    load_dotenv()
    recipients = [
        email.strip()
        for email in os.getenv("EMAIL_TO", "").split(",")
        if email.strip()
    ]
    return RuntimeConfig(
        db_path=Path(db_path or os.getenv("DB_PATH", "data/monitor.sqlite")),
        email_backend=os.getenv("EMAIL_BACKEND", "smtp").strip().lower(),
        email_from=os.getenv("EMAIL_FROM", "").strip(),
        email_to=recipients,
        send_empty_digest=coerce_bool(os.getenv("SEND_EMPTY_DIGEST"), default=False),
        max_items_per_digest=int(os.getenv("MAX_ITEMS_PER_DIGEST", "30")),
        local_timezone=os.getenv("LOCAL_TIMEZONE", "America/New_York"),
        llm_classifier_enabled=coerce_bool(os.getenv("LLM_CLASSIFIER_ENABLED"), default=False),
        openai_model=os.getenv("OPENAI_MODEL") or None,
        openai_reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "low").strip().lower() or "low",
    )


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def enabled_sources(sources_config: dict[str, Any]) -> list[dict[str, Any]]:
    sources = sources_config.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources.yaml must contain a 'sources' list")
    return [source for source in sources if coerce_bool(source.get("enabled"), default=True)]


def iter_source_queries(
    source: dict[str, Any],
    queries_config: dict[str, Any],
) -> list[tuple[str, str]]:
    groups = queries_config.get("query_groups", {})
    if not isinstance(groups, dict):
        raise ValueError("queries.yaml must contain a 'query_groups' mapping")

    selected_group_names = source.get("query_groups") or list(groups.keys())
    pairs: list[tuple[str, str]] = []
    for group_name in selected_group_names:
        queries = groups.get(group_name, [])
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            raise ValueError(f"Query group '{group_name}' must be a list or string")
        for query in queries:
            query_text = str(query).strip()
            if query_text:
                pairs.append((str(group_name), query_text))
    return pairs
