"""운영자 업로드 API 토큰 인증.

토큰은 scripts/generate_admin_token.py로 직접 생성해서 환경변수 ADMIN_UPLOAD_TOKEN에
등록합니다. 코드에는 어떤 값도 하드코딩하지 않습니다.

요청 헤더: Authorization: Bearer <ADMIN_UPLOAD_TOKEN>
"""
from __future__ import annotations

import hmac

from fastapi import Header

from app.core.config import ADMIN_UPLOAD_TOKEN
from app.core.errors import UnauthorizedError


def verify_admin_token(authorization: str | None = Header(default=None)) -> None:
    if not ADMIN_UPLOAD_TOKEN:
        # 서버에 토큰이 설정 안 된 상태는 항상 거부 (안전 기본값)
        raise UnauthorizedError("서버에 관리자 토큰이 설정되어 있지 않습니다.")

    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError()

    token = authorization.removeprefix("Bearer ").strip()

    if not hmac.compare_digest(token, ADMIN_UPLOAD_TOKEN):
        raise UnauthorizedError()
