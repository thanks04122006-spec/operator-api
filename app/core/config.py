"""전역 설정값"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
RECORDS_PATH = DATA_DIR / "records.json"
RECORDS_TMP_PATH = DATA_DIR / "records.tmp.json"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
UPLOAD_LOG_PATH = LOG_DIR / "upload_log.csv"

LIBRARY_NAME = "용산꿈나무도서관"
AVAILABLE_HOURS = list(range(8, 24))  # 8~23
LEVELS = {"quiet": "여유", "normal": "보통", "busy": "혼잡"}
OPERATING_HOURS = {
    "weekday": {"open": "09:00", "close": "21:00"},
    "weekend": {"open": "09:00", "close": "17:00"},
}

GATE_NAME_MAP = {"자료실.정문": "front", "자료실.후문": "back"}

# 혼잡도 3단계 경계(백분위). congestion.py(T04) 기준과 동일: 35 이하 quiet, 70 이하 normal, 초과 busy
CONGESTION_QUIET_MAX = 35.0
CONGESTION_NORMAL_MAX = 70.0

BASELINE_WEEKS = 4

# 운영자 업로드 토큰 — 반드시 환경변수로만 주입 (scripts/generate_admin_token.py 참고)
ADMIN_UPLOAD_TOKEN = os.environ.get("ADMIN_UPLOAD_TOKEN")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_KEEP_COUNT = 10

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
