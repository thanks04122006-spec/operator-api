"""업로드 시각·결과·오류를 CSV 로그로 기록"""
from __future__ import annotations

import csv
from datetime import datetime, timezone

from app.core.config import UPLOAD_LOG_PATH

_FIELDS = ["timestamp", "result", "record_count", "error_code", "error_summary", "warning_count", "backup_file"]


def _ensure_header() -> None:
    if not UPLOAD_LOG_PATH.exists():
        with open(UPLOAD_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=_FIELDS).writeheader()


def log_upload(
    result: str,
    record_count: int = 0,
    error_code: str | None = None,
    error_summary: str | None = None,
    warning_count: int = 0,
    backup_file: str | None = None,
) -> None:
    """result: 'success' | 'rejected' | 'error'"""
    _ensure_header()
    with open(UPLOAD_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": result,
                "record_count": record_count,
                "error_code": error_code or "",
                "error_summary": (error_summary or "")[:300],
                "warning_count": warning_count,
                "backup_file": backup_file or "",
            }
        )
