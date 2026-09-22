"""POST /api/v1/admin/records

도서관 PC 갱신 프로그램이 이미 전처리한 records.json을 이 엔드포인트로 전송합니다.

처리 순서:
1) 토큰 인증
2) Content-Type / 요청 크기 제한 확인
3) JSON 파싱
4) 스키마 검증 (하드 실패: 필드/타입, 요일 불일치, GATE_ROW_DUPLICATED)
   + 품질 경고 수집 (HOURLY_TOTAL_MISMATCH — 업로드는 그대로 진행)
5) 검증 통과 시에만 기존 파일 백업 → 임시파일 기록 → 원자적 교체
6) 업로드 로그 기록
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.core.admin_auth import verify_admin_token
from app.core.config import MAX_UPLOAD_BYTES
from app.core.errors import AppError, InvalidJsonError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.models.schemas import AdminUploadResult
from app.services import records_store, upload_log
from app.services.validation import validate_records

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/records", response_model=AdminUploadResult, dependencies=[Depends(verify_admin_token)])
async def upload_records(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        upload_log.log_upload(result="rejected", error_code="UNSUPPORTED_MEDIA_TYPE")
        raise UnsupportedMediaTypeError()

    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        upload_log.log_upload(result="rejected", error_code="PAYLOAD_TOO_LARGE")
        raise PayloadTooLargeError()

    import json

    try:
        raw = json.loads(body.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        upload_log.log_upload(result="rejected", error_code="INVALID_JSON")
        raise InvalidJsonError()

    try:
        records, warnings = validate_records(raw)
    except AppError as exc:
        upload_log.log_upload(result="rejected", error_code=exc.code, error_summary=exc.message)
        raise

    records_dict = [r.model_dump(mode="json", exclude_none=True) for r in records]
    backup_name = records_store.atomic_replace(records_dict)

    uploaded_at = datetime.now(timezone.utc).isoformat()
    upload_log.log_upload(
        result="success",
        record_count=len(records),
        warning_count=len(warnings),
        backup_file=backup_name,
    )

    return AdminUploadResult(
        accepted=True,
        record_count=len(records),
        previous_backup=backup_name,
        warnings=warnings,
        uploaded_at=uploaded_at,
    )
