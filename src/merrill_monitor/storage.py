from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from .models import CandidateItem, ClassifiedItem


LOGGER = logging.getLogger(__name__)


class SeenStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_results (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL,
                    normalized_url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    snippet TEXT,
                    summary TEXT,
                    published_date TEXT,
                    first_seen_date TEXT NOT NULL,
                    last_seen_date TEXT NOT NULL,
                    last_notified_date TEXT,
                    category TEXT,
                    sentiment TEXT,
                    relevance_score INTEGER,
                    is_accolade INTEGER,
                    is_forum_discussion INTEGER,
                    action_recommendation TEXT,
                    raw_json TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_source ON seen_results(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_category ON seen_results(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_last_seen ON seen_results(last_seen_date)")
            self._ensure_column(conn, "summary", "TEXT")
            self._ensure_column(conn, "last_notified_date", "TEXT")

    def _ensure_column(self, conn: sqlite3.Connection, column_name: str, column_type: str) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(seen_results)").fetchall()}
        if column_name not in existing:
            conn.execute(f"ALTER TABLE seen_results ADD COLUMN {column_name} {column_type}")

    def get_by_normalized_url(self, normalized_url: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM seen_results WHERE normalized_url = ?",
                (normalized_url,),
            ).fetchone()

    def touch_seen(self, candidate: CandidateItem, seen_date: str) -> None:
        if not candidate.normalized_url:
            return
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE seen_results
                SET last_seen_date = ?,
                    source = COALESCE(NULLIF(?, ''), source),
                    title = COALESCE(NULLIF(?, ''), title),
                    snippet = COALESCE(NULLIF(?, ''), snippet),
                    published_date = COALESCE(NULLIF(?, ''), published_date)
                WHERE normalized_url = ?
                """,
                (
                    seen_date,
                    candidate.source,
                    candidate.title,
                    candidate.snippet,
                    candidate.published_date or "",
                    candidate.normalized_url,
                ),
            )

    def insert_new(self, item: ClassifiedItem, seen_date: str) -> bool:
        if not item.normalized_url:
            LOGGER.warning("Skipping item without normalized URL: %s", item.title)
            return False
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO seen_results (
                        id,
                        source,
                        url,
                        normalized_url,
                        title,
                        snippet,
                        summary,
                        published_date,
                        first_seen_date,
                        last_seen_date,
                        category,
                        sentiment,
                        relevance_score,
                        is_accolade,
                        is_forum_discussion,
                        action_recommendation,
                        raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        item.source,
                        item.url,
                        item.normalized_url,
                        item.title,
                        item.snippet,
                        item.summary,
                        item.published_date,
                        seen_date,
                        seen_date,
                        item.category,
                        item.sentiment,
                        item.relevance_score,
                        int(item.is_accolade),
                        int(item.is_forum_discussion),
                        item.action_recommendation,
                        json.dumps(item.raw_json, ensure_ascii=False),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            LOGGER.info("Duplicate result already exists: %s", item.normalized_url)
            return False

    def mark_notified(self, item_ids: list[str], notified_date: str) -> None:
        if not item_ids:
            return
        placeholders = ",".join("?" for _ in item_ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE seen_results SET last_notified_date = ? WHERE id IN ({placeholders})",
                [notified_date, *item_ids],
            )

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM seen_results").fetchone()
            return int(row["count"])

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM seen_results
                ORDER BY first_seen_date DESC, relevance_score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
