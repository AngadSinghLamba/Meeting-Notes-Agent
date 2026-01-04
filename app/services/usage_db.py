from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class UsageEvent:
    tenant_id: str
    user_id: str
    request_id: str
    endpoint: str
    source: str               # text | image | pdf
    ocr_used: bool
    ocr_pages: int
    token_estimate: int       # simple estimate (we’ll compute later)
    created_at_utc: str


def _db_path() -> str:
    # store in repo-local data folder by default (good for portfolio)
    return os.getenv("USAGE_DB_PATH", "data/usage.db")


def init_db() -> None:
    os.makedirs(os.path.dirname(_db_path()), exist_ok=True)

    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                source TEXT NOT NULL,
                ocr_used INTEGER NOT NULL,
                ocr_pages INTEGER NOT NULL,
                token_estimate INTEGER NOT NULL,
                created_at_utc TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_tenant_user_time ON usage_events(tenant_id, user_id, created_at_utc);"
        )
        conn.commit()


def log_event(event: UsageEvent) -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO usage_events
            (tenant_id, user_id, request_id, endpoint, source, ocr_used, ocr_pages, token_estimate, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event.tenant_id,
                event.user_id,
                event.request_id,
                event.endpoint,
                event.source,
                1 if event.ocr_used else 0,
                event.ocr_pages,
                event.token_estimate,
                event.created_at_utc,
            ),
        )
        conn.commit()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def list_events(tenant_id: str, user_id: str | None = None, limit: int = 20) -> list[dict]:
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    where = "tenant_id = ?"
    params: list = [tenant_id]

    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    params.append(limit)

    sql = f"""
        SELECT
            id, tenant_id, user_id, request_id, endpoint, source,
            ocr_used, ocr_pages, token_estimate, created_at_utc
        FROM usage_events
        WHERE {where}
        ORDER BY id DESC
        LIMIT ?;
    """

    with sqlite3.connect(_db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()

    results = []
    for r in rows:
        results.append(
            {
                "id": r[0],
                "tenant_id": r[1],
                "user_id": r[2],
                "request_id": r[3],
                "endpoint": r[4],
                "source": r[5],
                "ocr_used": bool(r[6]),
                "ocr_pages": int(r[7]),
                "token_estimate": int(r[8]),
                "created_at_utc": r[9],
            }
        )
    return results

def count_ocr_split(tenant_id: str, user_id: str | None = None) -> tuple[int, int]:
    """
    Returns: (ocr_requests, non_ocr_requests) for a tenant (optionally filtered by user).
    """
    where = "tenant_id = ?"
    params: list = [tenant_id]

    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    sql = f"""
        SELECT
          COALESCE(SUM(CASE WHEN ocr_used = 1 THEN 1 ELSE 0 END), 0) AS ocr_requests,
          COALESCE(SUM(CASE WHEN ocr_used = 0 THEN 1 ELSE 0 END), 0) AS non_ocr_requests
        FROM usage_events
        WHERE {where};
    """

    with sqlite3.connect(_db_path()) as conn:
        row = conn.execute(sql, params).fetchone()

    ocr_requests = int(row[0] or 0)
    non_ocr_requests = int(row[1] or 0)
    return ocr_requests, non_ocr_requests
