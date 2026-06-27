from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .classifier import ItemClassifier
from .config import enabled_sources, iter_source_queries, load_runtime_config, load_yaml_file
from .digest import build_email_digest
from .emailer import send_email
from .brave_search import BraveSearchClient
from .logging_config import configure_logging
from .models import CandidateItem, ClassifiedItem
from .storage import SeenStore
from .utils import coerce_bool, today_iso


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Merrill Edge daily monitor.")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Fetch, dedupe, classify, and send the daily digest.")
    run_parser.add_argument("--sources", default="sources.yaml", help="Path to sources.yaml")
    run_parser.add_argument("--queries", default="queries.yaml", help="Path to queries.yaml")
    run_parser.add_argument("--db", default=None, help="Override SQLite database path")
    mode_group = run_parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="Print digest without sending email or writing SQLite")
    mode_group.add_argument("--baseline", action="store_true", help="Store current results as seen without sending email")
    run_parser.add_argument("--send-empty", action="store_true", help="Send a digest even when there are no new items")

    subparsers.add_parser("init-db", help="Create or migrate the SQLite database.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"

    runtime = load_runtime_config(getattr(args, "db", None))
    configure_logging()

    if command == "init-db":
        SeenStore(runtime.db_path)
        LOGGER.info("Initialized database at %s", runtime.db_path)
        return 0
    if command == "run":
        return run_monitor(args, runtime)

    parser.print_help()
    return 2


def run_monitor(args: argparse.Namespace, runtime) -> int:
    run_date = today_iso(runtime.local_timezone)
    sources_config = load_yaml_file(args.sources)
    queries_config = load_yaml_file(args.queries)
    sources = enabled_sources(sources_config)
    store = SeenStore(runtime.db_path)
    classifier = ItemClassifier(
        use_llm=runtime.llm_classifier_enabled,
        openai_model=runtime.openai_model,
        openai_reasoning_effort=runtime.openai_reasoning_effort,
    )

    LOGGER.info("Starting Merrill Edge monitor for %s with %d enabled sources", run_date, len(sources))
    candidates = collect_candidates(sources, queries_config)
    deduped_candidates = dedupe_candidates(candidates)
    LOGGER.info("Collected %d candidates, %d after in-batch dedupe", len(candidates), len(deduped_candidates))

    new_items: list[ClassifiedItem] = []
    seen_count = 0
    dry_run = getattr(args, "dry_run", False)
    baseline = getattr(args, "baseline", False)
    for candidate in deduped_candidates:
        if store.get_by_normalized_url(candidate.normalized_url):
            seen_count += 1
            if not dry_run:
                store.touch_seen(candidate, run_date)
            continue
        item = classifier.classify(candidate)
        if dry_run:
            new_items.append(item)
        elif store.insert_new(item, run_date):
            new_items.append(item)

    new_items = sorted(new_items, key=lambda item: item.relevance_score, reverse=True)
    if baseline:
        store.mark_notified([item.id for item in new_items], run_date)
        LOGGER.info(
            "Baseline complete; stored %d new items, touched %d existing items, email not sent",
            len(new_items),
            seen_count,
        )
        print(f"Baseline complete: stored {len(new_items)} new items and touched {seen_count} existing items.")
        return 0

    if runtime.max_items_per_digest > 0:
        new_items = new_items[: runtime.max_items_per_digest]

    subject, body = build_email_digest(new_items, run_date)
    should_send = bool(new_items) or runtime.send_empty_digest or getattr(args, "send_empty", False)
    if getattr(args, "dry_run", False):
        print(subject)
        print()
        print(body)
        LOGGER.info("Dry run complete; database unchanged and email not sent")
        return 0

    if not should_send:
        LOGGER.info("No new items found and SEND_EMPTY_DIGEST=false; email suppressed")
        return 0

    send_email(
        subject=subject,
        body=body,
        sender=runtime.email_from,
        recipients=runtime.email_to,
        backend=runtime.email_backend,
    )
    store.mark_notified([item.id for item in new_items], run_date)
    LOGGER.info("Monitor complete; sent %d new items", len(new_items))
    return 0


def collect_candidates(
    sources: list[dict],
    queries_config: dict,
) -> list[CandidateItem]:
    brave_client = BraveSearchClient()
    candidates: list[CandidateItem] = []

    for source in sources:
        source_type = str(source.get("type", "")).strip().lower()
        source_name = str(source.get("name", source_type)).strip()
        query_pairs = iter_source_queries(source, queries_config)
        LOGGER.info("Running source=%s type=%s with %d queries", source_name, source_type, len(query_pairs))

        if source_type == "brave_search":
            if not brave_client.is_configured:
                LOGGER.warning("Brave Search is not configured; skipping source=%s", source_name)
                continue
            for query_group, query in query_pairs:
                candidates.extend(
                    brave_client.search(
                        source_name=source_name,
                        query_group=query_group,
                        query=query,
                        result_limit=int(source.get("result_limit", 10)),
                        freshness=source.get("freshness"),
                        safesearch=source.get("safesearch", "moderate"),
                        country=source.get("country", "US"),
                        search_lang=source.get("search_lang", "en"),
                        site_restrict=source.get("site_restrict"),
                        is_forum_discussion=coerce_bool(source.get("is_forum_discussion"), default=False),
                    )
                )
        else:
            LOGGER.warning("Unknown source type %r for source %s; skipping", source_type, source_name)
    return candidates


def dedupe_candidates(candidates: list[CandidateItem]) -> list[CandidateItem]:
    seen: set[str] = set()
    deduped: list[CandidateItem] = []
    for candidate in candidates:
        key = candidate.normalized_url
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
