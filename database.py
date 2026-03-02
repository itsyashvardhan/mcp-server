"""
SQLite database layer for the Job Listings MCP Server.

Features:
  - Auto-creates the `jobs` table on first run.
  - Deduplicates on (job_title, company, location) via UNIQUE constraint.
  - Provides flexible query with optional filters.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from config import DB_PATH

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title       TEXT    NOT NULL,
    company         TEXT    NOT NULL,
    location        TEXT    NOT NULL DEFAULT '',
    salary          TEXT    DEFAULT '',
    apply_link      TEXT    DEFAULT '',
    description     TEXT    DEFAULT '',
    date_posted     TEXT    DEFAULT '',
    date_scraped    TEXT    NOT NULL,
    source_site     TEXT    DEFAULT '',
    role_tier       TEXT    DEFAULT '',
    UNIQUE(job_title, company, location)
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_jobs_date_scraped ON jobs(date_scraped);
CREATE INDEX IF NOT EXISTS idx_jobs_location     ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_jobs_job_title    ON jobs(job_title);
"""


def get_connection() -> sqlite3.Connection:
    """Return a new connection with WAL mode and row factory."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


@contextmanager
def get_db():
    """Context manager that yields a connection and auto-closes."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    with get_db() as conn:
        conn.executescript(CREATE_TABLE_SQL + CREATE_INDEX_SQL)
        conn.commit()


def insert_jobs(jobs: list[dict[str, Any]]) -> int:
    """
    Insert a batch of jobs with deduplication.
    Returns the number of newly inserted rows.
    """
    if not jobs:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with get_db() as conn:
        for job in jobs:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs
                        (job_title, company, location, salary, apply_link,
                         description, date_posted, date_scraped, source_site, role_tier)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.get("job_title", "").strip(),
                        job.get("company", "").strip(),
                        job.get("location", "").strip(),
                        job.get("salary", ""),
                        job.get("apply_link", ""),
                        job.get("description", ""),
                        job.get("date_posted", ""),
                        now,
                        job.get("source_site", ""),
                        job.get("role_tier", ""),
                    ),
                )
                inserted += conn.total_changes  # Running total — we'll reconcile below
            except sqlite3.IntegrityError:
                pass
        conn.commit()

    return inserted


def insert_jobs_bulk(jobs: list[dict[str, Any]]) -> int:
    """
    Bulk insert with executemany and INSERT OR IGNORE.
    Returns approximate count of new inserts.
    """
    if not jobs:
        return 0

    now = datetime.now(timezone.utc).isoformat()

    rows = [
        (
            job.get("job_title", "").strip(),
            job.get("company", "").strip(),
            job.get("location", "").strip(),
            job.get("salary", ""),
            job.get("apply_link", ""),
            job.get("description", ""),
            job.get("date_posted", ""),
            now,
            job.get("source_site", ""),
            job.get("role_tier", ""),
        )
        for job in jobs
    ]

    with get_db() as conn:
        before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.executemany(
            """
            INSERT OR IGNORE INTO jobs
                (job_title, company, location, salary, apply_link,
                 description, date_posted, date_scraped, source_site, role_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    return after - before

def query_jobs(
    location: str | None = None,
    keyword: str | None = None,
    hours: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Query jobs with optional filters.

    Args:
        location: Filter by location (case-insensitive substring match).
        keyword:  Filter by keyword in job_title (case-insensitive substring).
        hours:    Only return jobs scraped within the last N hours.
        limit:    Max results (default 100).
        offset:   Pagination offset.

    Returns:
        List of job dicts.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if location:
        clauses.append("LOWER(location) LIKE ?")
        params.append(f"%{location.lower()}%")

    if keyword:
        clauses.append("LOWER(job_title) LIKE ?")
        params.append(f"%{keyword.lower()}%")

    if hours and hours > 0:
        clauses.append("date_scraped >= datetime('now', ?)")
        params.append(f"-{hours} hours")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    sql = f"""
        SELECT id, job_title, company, location, salary, apply_link,
               date_posted, date_scraped, source_site, role_tier
        FROM jobs
        {where}
        ORDER BY date_scraped DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def count_jobs() -> int:
    """Return total number of jobs in the database."""
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
