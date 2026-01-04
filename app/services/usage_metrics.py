from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class UsageSummary:
    tenant_id: str
    user_id: Optional[str]

    total_requests: int
    total_ocr_pages: int
    total_token_estimate: int

    llm_cost_usd_est: float
    ocr_cost_usd_est: float
    total_cost_usd_est: float


def _db_path() -> str:
    return os.getenv("USAGE_DB_PATH", "data/usage.db")


def _llm_cost_per_1k_tokens_usd() -> float:
    # Keep this configurable because pricing/model changes.
    # Put your chosen estimate in .env (example): LLM_COST_PER_1K_TOKENS_USD=0.001
    return float(os.getenv("LLM_COST_PER_1K_TOKENS_USD", "0.0"))


def _ocr_cost_per_page_usd() -> float:
    # Put your chosen estimate in .env (example): OCR_COST_PER_PAGE_USD=0.0015
    return float(os.getenv("OCR_COST_PER_PAGE_USD", "0.0"))


def get_usage_summary(tenant_id: str, user_id: Optional[str] = None) -> UsageSummary:
    """
    Aggregates usage by tenant (and optional user) from SQLite.

    Note: token_estimate is a heuristic for now (len(text)//4).
    For portfolio: this is fine as "estimated usage/cost".
    """
    where = "tenant_id = ?"
    params = [tenant_id]

    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    sql = f"""
        SELECT
            COUNT(*) as total_requests,
            COALESCE(SUM(ocr_pages), 0) as total_ocr_pages,
            COALESCE(SUM(token_estimate), 0) as total_token_estimate
        FROM usage_events
        WHERE {where};
    """

    with sqlite3.connect(_db_path()) as conn:
        row = conn.execute(sql, params).fetchone()

    total_requests = int(row[0] or 0)
    total_ocr_pages = int(row[1] or 0)
    total_token_estimate = int(row[2] or 0)

    llm_cost = (total_token_estimate / 1000.0) * _llm_cost_per_1k_tokens_usd()
    ocr_cost = total_ocr_pages * _ocr_cost_per_page_usd()
    total_cost = llm_cost + ocr_cost

    return UsageSummary(
        tenant_id=tenant_id,
        user_id=user_id,
        total_requests=total_requests,
        total_ocr_pages=total_ocr_pages,
        total_token_estimate=total_token_estimate,
        llm_cost_usd_est=round(llm_cost, 6),
        ocr_cost_usd_est=round(ocr_cost, 6),
        total_cost_usd_est=round(total_cost, 6),
    )


def to_dict(summary: UsageSummary) -> Dict[str, Any]:
    return {
        "tenant_id": summary.tenant_id,
        "user_id": summary.user_id,
        "total_requests": summary.total_requests,
        "total_ocr_pages": summary.total_ocr_pages,
        "total_token_estimate": summary.total_token_estimate,
        "llm_cost_usd_est": summary.llm_cost_usd_est,
        "ocr_cost_usd_est": summary.ocr_cost_usd_est,
        "total_cost_usd_est": summary.total_cost_usd_est,
        "assumptions": {
            "LLM_COST_PER_1K_TOKENS_USD": _llm_cost_per_1k_tokens_usd(),
            "OCR_COST_PER_PAGE_USD": _ocr_cost_per_page_usd(),
            "token_estimate_method": "len(text)//4 (input only)",
        },
    }
