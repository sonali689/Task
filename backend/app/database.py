"""
SQLite storage layer for billing data and computed reports.

Uses in-memory or file-based SQLite. Stores raw validated records
and pre-computed reconciliation/analytics for fast retrieval.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Database file path — use a file in the backend directory
DB_PATH = Path(__file__).parent.parent / "swasthiq.db"


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS billing_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clinic_id TEXT NOT NULL,
                date TEXT NOT NULL,
                raw_data TEXT NOT NULL,
                valid_count INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                validation_errors TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(clinic_id, date)
            );

            CREATE TABLE IF NOT EXISTS billing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER NOT NULL,
                clinic_id TEXT NOT NULL,
                visit_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                line_items TEXT NOT NULL,
                payment_mode TEXT NOT NULL,
                amount_paid_paise INTEGER NOT NULL,
                discount_paise INTEGER NOT NULL DEFAULT 0,
                is_refund BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (upload_id) REFERENCES billing_uploads(id)
            );

            CREATE TABLE IF NOT EXISTS reconciliation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clinic_id TEXT NOT NULL,
                date TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(clinic_id, date)
            );

            CREATE TABLE IF NOT EXISTS analytics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clinic_id TEXT NOT NULL,
                date TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(clinic_id, date)
            );
        """)


def store_upload(
    conn: sqlite3.Connection,
    clinic_id: str,
    date: str,
    raw_data: str,
    valid_count: int,
    error_count: int,
    validation_errors: str,
) -> int:
    """Store an upload record, replacing any existing one for the same clinic+date."""
    # Delete existing data for this clinic+date
    existing = conn.execute(
        "SELECT id FROM billing_uploads WHERE clinic_id = ? AND date = ?",
        (clinic_id, date),
    ).fetchone()

    if existing:
        upload_id = existing["id"]
        conn.execute("DELETE FROM billing_records WHERE upload_id = ?", (upload_id,))
        conn.execute("DELETE FROM billing_uploads WHERE id = ?", (upload_id,))
        conn.execute(
            "DELETE FROM reconciliation_cache WHERE clinic_id = ? AND date = ?",
            (clinic_id, date),
        )
        conn.execute(
            "DELETE FROM analytics_cache WHERE clinic_id = ? AND date = ?",
            (clinic_id, date),
        )

    cursor = conn.execute(
        """INSERT INTO billing_uploads
           (clinic_id, date, raw_data, valid_count, error_count, validation_errors)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (clinic_id, date, raw_data, valid_count, error_count, validation_errors),
    )
    return cursor.lastrowid


def store_records(
    conn: sqlite3.Connection,
    upload_id: int,
    records: list,
) -> None:
    """Store validated billing records."""
    for r in records:
        conn.execute(
            """INSERT INTO billing_records
               (upload_id, clinic_id, visit_id, timestamp, doctor_id,
                line_items, payment_mode, amount_paid_paise,
                discount_paise, is_refund)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                upload_id,
                r.clinic_id,
                r.visit_id,
                r.timestamp.isoformat(),
                r.doctor_id,
                json.dumps([item.model_dump() for item in r.line_items]),
                r.payment_mode.value,
                r.amount_paid_paise,
                r.discount_paise,
                r.is_refund,
            ),
        )


def cache_reconciliation(
    conn: sqlite3.Connection,
    clinic_id: str,
    date: str,
    report_json: str,
) -> None:
    """Cache the reconciliation report."""
    conn.execute(
        """INSERT OR REPLACE INTO reconciliation_cache
           (clinic_id, date, report_json) VALUES (?, ?, ?)""",
        (clinic_id, date, report_json),
    )


def get_cached_reconciliation(
    conn: sqlite3.Connection,
    clinic_id: str,
    date: str,
) -> str | None:
    """Retrieve cached reconciliation report JSON."""
    row = conn.execute(
        "SELECT report_json FROM reconciliation_cache WHERE clinic_id = ? AND date = ?",
        (clinic_id, date),
    ).fetchone()
    return row["report_json"] if row else None


def cache_analytics(
    conn: sqlite3.Connection,
    clinic_id: str,
    date: str,
    report_json: str,
) -> None:
    """Cache the analytics report."""
    conn.execute(
        """INSERT OR REPLACE INTO analytics_cache
           (clinic_id, date, report_json) VALUES (?, ?, ?)""",
        (clinic_id, date, report_json),
    )


def get_cached_analytics(
    conn: sqlite3.Connection,
    clinic_id: str,
    date: str,
) -> str | None:
    """Retrieve cached analytics report JSON."""
    row = conn.execute(
        "SELECT report_json FROM analytics_cache WHERE clinic_id = ? AND date = ?",
        (clinic_id, date),
    ).fetchone()
    return row["report_json"] if row else None


def get_available_dates(conn: sqlite3.Connection) -> list[dict]:
    """List all available clinic+date combinations."""
    rows = conn.execute(
        """SELECT clinic_id, date, valid_count as record_count
           FROM billing_uploads ORDER BY date DESC"""
    ).fetchall()
    return [dict(row) for row in rows]
