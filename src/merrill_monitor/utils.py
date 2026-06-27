from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() not in TRACKING_QUERY_PARAMS and not key.lower().startswith("utm_")
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_url_with_content_signature(url: str, *values: str | None) -> str:
    normalized = normalize_url(url)
    signature_seed = compact_whitespace(" ".join(value or "" for value in values))
    if not normalized or not signature_seed:
        return normalized

    signature = hashlib.sha256(signature_seed.encode("utf-8")).hexdigest()[:16]
    parts = urlsplit(normalized)
    query_pairs = parse_qsl(parts.query, keep_blank_values=False)
    query_pairs.append(("monitor_sig", signature))
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def stable_id(source: str, normalized_url: str, title: str = "") -> str:
    seed = f"{source}|{normalized_url or title}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:32]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_iso(tz_name: str | None = None) -> str:
    tz = timezone.utc
    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            tz = timezone.utc
    return datetime.now(tz).date().isoformat()


def coerce_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def trim_text(value: str, max_chars: int = 280) -> str:
    value = compact_whitespace(value)
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


def first_nonempty(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            stripped = compact_whitespace(value)
            if stripped:
                return stripped
    return None


def two_sentence_summary(title: str, snippet: str, category: str | None = None) -> str:
    title = trim_text(title, 180)
    snippet = trim_text(snippet, 240)
    if not title and not snippet:
        base = "A Merrill Edge mention was found."
    elif title and snippet:
        base = f"{title}. {snippet}"
    else:
        base = title or snippet

    sentences = split_sentences(base)
    if len(sentences) >= 2:
        return " ".join(sentences[:2])
    if category:
        return f"{sentences[0] if sentences else base}. Classified as {category}."
    return f"{sentences[0] if sentences else base}. Monitor for follow-up context."


def split_sentences(text: str) -> list[str]:
    text = compact_whitespace(text)
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", text)
    sentences = [piece.strip() for piece in pieces if piece.strip()]
    normalized = []
    for sentence in sentences:
        if sentence[-1] not in ".!?":
            sentence += "."
        normalized.append(sentence)
    return normalized
