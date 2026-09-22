"""records.json 을 임시파일에 먼저 쓰고 검증 후 원자적으로 교체.

- 교체 직전 기존 파일을 backups/ 로 복사
- 검증 실패 시 아무것도 건드리지 않음 → 기존 파일이 곧 마지막 정상본
- os.replace() 는 POSIX/Windows 모두 원자적 rename을 보장
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.core.config import BACKUP_DIR, BACKUP_KEEP_COUNT, RECORDS_PATH, RECORDS_TMP_PATH

_lock = Lock()


def load_records() -> list[dict]:
    if not RECORDS_PATH.exists():
        return []
    with open(RECORDS_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _backup_current() -> str | None:
    if not RECORDS_PATH.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = f"records_{stamp}.json"
    shutil.copy2(RECORDS_PATH, BACKUP_DIR / name)
    _prune_old_backups()
    return name


def _prune_old_backups() -> None:
    backups = sorted(BACKUP_DIR.glob("records_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[BACKUP_KEEP_COUNT:]:
        old.unlink(missing_ok=True)


def atomic_replace(records: list[dict]) -> str | None:
    """검증이 끝난 records(dict 리스트)를 records.json에 원자적으로 반영.
    반환값: 백업 파일명 (기존 파일이 없었으면 None)
    """
    with _lock:
        backup_name = _backup_current()
        with open(RECORDS_TMP_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(RECORDS_TMP_PATH, RECORDS_PATH)
        return backup_name


def restore_from_backup(backup_name: str) -> None:
    backup_path = BACKUP_DIR / backup_name
    if not backup_path.exists():
        raise FileNotFoundError(f"백업 파일을 찾을 수 없습니다: {backup_name}")
    with _lock:
        shutil.copy2(backup_path, RECORDS_PATH)
