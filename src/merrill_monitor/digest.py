from __future__ import annotations

from collections import Counter, defaultdict

from .models import ClassifiedItem


def build_email_digest(items: list[ClassifiedItem], run_date: str) -> tuple[str, str]:
    subject = f"Merrill Edge Daily Monitor — {len(items)} new items"
    ordered = sorted(items, key=lambda item: item.relevance_score, reverse=True)

    lines: list[str] = []
    lines.append(f"Merrill Edge Daily Monitor for {run_date}")
    lines.append("")
    lines.append("1. Executive summary")
    if not ordered:
        lines.append("No new or strategically meaningful items were found in today's configured sources.")
        return subject, "\n".join(lines)

    category_counts = Counter(item.category for item in ordered)
    sentiment_counts = Counter(item.sentiment for item in ordered)
    high_count = sum(1 for item in ordered if item.relevance_label == "high")
    negative_count = sum(1 for item in ordered if item.sentiment in {"negative", "mixed"})
    lines.append(
        f"Found {len(ordered)} new items: {high_count} high relevance, "
        f"{negative_count} negative or mixed, and {sum(1 for item in ordered if item.is_accolade)} accolades."
    )
    lines.append("Top categories: " + format_counts(category_counts))
    lines.append("Sentiment mix: " + format_counts(sentiment_counts))
    lines.append("")

    lines.append("2. New accolades")
    add_item_section(lines, [item for item in ordered if item.is_accolade])
    lines.append("")

    lines.append("3. Forum themes")
    forum_items = [item for item in ordered if item.is_forum_discussion]
    if forum_items:
        forum_counts = Counter(item.category for item in forum_items)
        lines.append("Theme mix: " + format_counts(forum_counts))
    add_item_section(lines, forum_items)
    lines.append("")

    lines.append("4. Negative or high-risk mentions")
    risky_items = [
        item
        for item in ordered
        if item.sentiment in {"negative", "mixed"}
        or item.relevance_label == "high"
        or item.action_recommendation in {"escalate to product", "escalate to service", "competitive threat"}
    ]
    add_item_section(lines, risky_items)
    lines.append("")

    lines.append("5. Recommended actions")
    action_groups: dict[str, list[ClassifiedItem]] = defaultdict(list)
    for item in ordered:
        action_groups[item.action_recommendation].append(item)
    for action, action_items in sorted(action_groups.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        lines.append(f"- {action}: {len(action_items)}")
        for item in action_items[:5]:
            lines.append(f"  - {item.title} ({item.relevance_label}, {item.sentiment})")
    lines.append("")

    lines.append("6. Full source links")
    for index, item in enumerate(ordered, start=1):
        lines.append(f"{index}. {item.title}")
        lines.append(f"   Source: {item.source}")
        lines.append(f"   Category: {item.category}")
        lines.append(f"   Sentiment: {item.sentiment}")
        lines.append(f"   Relevance: {item.relevance_label} ({item.relevance_score})")
        lines.append(f"   Action: {item.action_recommendation}")
        lines.append(f"   Summary: {item.summary}")
        lines.append(f"   URL: {item.url}")
    return subject, "\n".join(lines)


def add_item_section(lines: list[str], items: list[ClassifiedItem], limit: int = 8) -> None:
    if not items:
        lines.append("None.")
        return
    for item in items[:limit]:
        lines.append(f"- [{item.relevance_label} | {item.sentiment}] {item.title}")
        lines.append(f"  Summary: {item.summary}")
        lines.append(f"  Category: {item.category}")
        lines.append(f"  Action: {item.action_recommendation}")
        lines.append(f"  Link: {item.url}")
    if len(items) > limit:
        lines.append(f"...and {len(items) - limit} more in the full source links section.")


def format_counts(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{name} ({count})" for name, count in counter.most_common(5))
