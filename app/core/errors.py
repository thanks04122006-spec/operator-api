"""7. API 공통 오류 응답 규격

{
  "error": { "code": "DATA_NOT_FOUND", "message": "..." }
}
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

STATUS_BY_CODE = {
    "DATA_NOT_FOUND": 404,
    "INVALID_DATE": 400,
    "EXCEL_FORMAT_ERROR": 422,
    "PROCESSING_ERROR": 422,
    "GATE_ROW_DUPLICATED": 422,
    # HOURLY_TOTAL_MISMATCH: 품질 경고 전용 코드. 업로드를 막지 않으므로
    # 여기 상태코드 매핑은 참고용이며 실제로 이 코드로 예외가 발생하는 일은 없음.
    "HOURLY_TOTAL_MISMATCH": 422,
    "UNAUTHORIZED": 401,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "PAYLOAD_TOO_LARGE": 413,
    "INVALID_JSON": 400,
}


class AppError(Exception):
    code = "PROCESSING_ERROR"

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        if code:
            self.code = code
        super().__init__(message)

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE.get(self.code, 500)


class DataNotFoundError(AppError):
    code = "DATA_NOT_FOUND"

    def __init__(self, message: str = "해당 날짜의 데이터를 찾을 수 없습니다."):
        super().__init__(message)


class InvalidDateError(AppError):
    code = "INVALID_DATE"

    def __init__(self, message: str = "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."):
        super().__init__(message)


class ProcessingError(AppError):
    code = "PROCESSING_ERROR"

    def __init__(self, message: str = "데이터 처리 중 오류가 발생했습니다."):
        super().__init__(message)


class GateRowDuplicatedError(AppError):
    code = "GATE_ROW_DUPLICATED"

    def __init__(self, message: str = "같은 날짜의 정문·후문 행이 중복되었습니다."):
        super().__init__(message)


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"

    def __init__(self, message: str = "인증 토큰이 없거나 올바르지 않습니다."):
        super().__init__(message)


class UnsupportedMediaTypeError(AppError):
    code = "UNSUPPORTED_MEDIA_TYPE"

    def __init__(self, message: str = "Content-Type은 application/json 이어야 합니다."):
        super().__init__(message)


class PayloadTooLargeError(AppError):
    code = "PAYLOAD_TOO_LARGE"

    def __init__(self, message: str = "요청 크기가 허용된 최대값을 초과했습니다."):
        super().__init__(message)


class InvalidJsonError(AppError):
    code = "INVALID_JSON"

    def __init__(self, message: str = "JSON 형식이 올바르지 않습니다."):
        super().__init__(message)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_error_body("PROCESSING_ERROR", f"예상하지 못한 오류가 발생했습니다: {exc}"),
        )
