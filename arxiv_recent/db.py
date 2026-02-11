"""SQLite persistence layer."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arxiv_recent.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    arxiv_id   TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    authors    TEXT NOT NULL,
    category   TEXT NOT NULL,
    published_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    abs_url    TEXT NOT NULL,
    pdf_url    TEXT NOT NULL,
    abstract   TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS summaries (
    arxiv_id     TEXT PRIMARY KEY REFERENCES papers(arxiv_id),
    summary_json TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    run_date      TEXT PRIMARY KEY,
    status        TEXT NOT NULL DEFAULT 'pending',
    sent_channels TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or get_settings().db_full_path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- papers --

    def upsert_paper(self, paper: dict[str, Any]) -> bool:
        """Insert or ignore a paper. Returns True if newly inserted."""
        cur = self._conn.execute(
            """INSERT OR IGNORE INTO papers
               (arxiv_id, title, authors, category, published_at,
                updated_at, abs_url, pdf_url, abstract, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                paper["arxiv_id"],
                paper["title"],
                paper["authors"],
                paper["category"],
                paper["published_at"],
                paper["updated_at"],
                paper["abs_url"],
                paper["pdf_url"],
                paper["abstract"],
                _now_iso(),
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def upsert_papers(self, papers: list[dict[str, Any]]) -> int:
        """Bulk upsert. Returns count of newly inserted."""
        inserted = 0
        for p in papers:
            if self.upsert_paper(p):
                inserted += 1
        return inserted

    def get_papers_without_summary(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT p.* FROM papers p
               LEFT JOIN summaries s ON p.arxiv_id = s.arxiv_id
               WHERE s.arxiv_id IS NULL
               ORDER BY p.published_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def get_papers_for_date(self, date_str: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT p.*, s.summary_json FROM papers p
               LEFT JOIN summaries s ON p.arxiv_id = s.arxiv_id
               WHERE date(p.fetched_at) = ?
               ORDER BY p.published_at DESC""",
            (date_str,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_papers_with_summaries(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT p.*, s.summary_json FROM papers p
               INNER JOIN summaries s ON p.arxiv_id = s.arxiv_id
               ORDER BY p.published_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # -- summaries --

    def has_summary(self, arxiv_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM summaries WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return row is not None

    def save_summary(self, arxiv_id: str, summary: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO summaries (arxiv_id, summary_json, created_at)
               VALUES (?, ?, ?)""",
            (arxiv_id, json.dumps(summary, ensure_ascii=False), _now_iso()),
        )
        self._conn.commit()

    def get_summary(self, arxiv_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT summary_json FROM summaries WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["summary_json"])

    # -- runs --

    def get_run(self, run_date: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM runs WHERE run_date = ?", (run_date,)).fetchone()
        return dict(row) if row else None

    def upsert_run(self, run_date: str, status: str, sent_channels: str = "") -> None:
        self._conn.execute(
            """INSERT INTO runs (run_date, status, sent_channels, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(run_date) DO UPDATE SET
                   status = excluded.status,
                   sent_channels = excluded.sent_channels""",
            (run_date, status, sent_channels, _now_iso()),
        )
        self._conn.commit()

    def was_sent(self, run_date: str, channel: str) -> bool:
        run = self.get_run(run_date)
        if run is None:
            return False
        return channel in run["sent_channels"].split(",")

    def mark_sent(self, run_date: str, channel: str) -> None:
        run = self.get_run(run_date)
        if run is None:
            self.upsert_run(run_date, "sent", channel)
            return
        existing = {c for c in run["sent_channels"].split(",") if c}
        existing.add(channel)
        self.upsert_run(run_date, "sent", ",".join(sorted(existing)))
