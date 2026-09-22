"""records 배열 검증.

- 스키마(필드/타입/범위) 오류, 요일 불일치, date+gate+hour 중복(GATE_ROW_DUPLICATED)은
  하드 실패 — 업로드 전체를 거부하고 기존 파일을 건드리지 않습니다.
- 시간대 합계 vs 일일 총량 불일치(HOURLY_TOTAL_MISMATCH)는 품질 경고 — 업로드는
  그대로 반영하고, 응답의 warnings 목록에만 남깁니다 (파이프라인 중단 아님).
"""
from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime

from pydantic import TypeAdapter, ValidationError

from app.core.errors import GateRowDuplicatedError, ProcessingError
from app.models.schemas import RecordItem

_WEEKDAY_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_records_adapter = TypeAdapter(list[RecordItem])


def parse_records(raw) -> list[RecordItem]:
    if not isinstance(raw, list):
        raise ProcessingError("records는 JSON 배열이어야 합니다.")
    try:
        return _records_adapter.validate_python(raw)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        raise ProcessingError(f"record 검증 실패 ({loc}): {first['msg']}")


def validate_records(raw) -> tuple[list[RecordItem], list[str]]:
    """검증 통과한 레코드 목록과 품질 경고 목록을 반환. 하드 실패는 예외로 던집니다."""
    records = parse_records(raw)
    if not records:
        raise ProcessingError("records 배열이 비어 있습니다.")

    seen_keys = set()
    groups: dict[tuple[str, str], list[RecordItem]] = {}

    for r in records:
        try:
            actual_date = date_cls.fromisoformat(r.date)
        except ValueError:
            raise ProcessingError(f"date 형식이 올바르지 않습니다: {r.date}")
        expected_dow = _WEEKDAY_EN[actual_date.weekday()]
        if r.day_of_week != expected_dow:
            raise ProcessingError(
                f"{r.date} {r.hour}시: day_of_week가 실제 요일({expected_dow})과 다릅니다."
            )

        key = (r.date, r.gate, r.hour)
        if key in seen_keys:
            raise GateRowDuplicatedError(f"중복된 date+gate+hour: {key}")
        seen_keys.add(key)

        groups.setdefault((r.date, r.gate), []).append(r)

    warnings: list[str] = []
    for (date_str, gate), rows in groups.items():
        hourly_in = sum(row.in_count for row in rows)
        hourly_out_values = [row.out_count for row in rows]
        claimed_total_in = rows[0].total_in
        claimed_total_out = rows[0].total_out

        if any(row.total_in != claimed_total_in or row.total_out != claimed_total_out for row in rows):
            warnings.append(f"{date_str}/{gate}: 레코드마다 total_in/total_out 값이 서로 다릅니다.")
        elif hourly_in != claimed_total_in:
            warnings.append(
                f"{date_str}/{gate}: 시간대 IN 합계({hourly_in})가 일일 total_in({claimed_total_in})과 다릅니다."
            )

        if None not in hourly_out_values:
            hourly_out = sum(hourly_out_values)
            if hourly_out != claimed_total_out:
                warnings.append(
                    f"{date_str}/{gate}: 시간대 OUT 합계({hourly_out})가 일일 total_out({claimed_total_out})과 다릅니다."
                )

    records_sorted = sorted(records, key=lambda r: (r.date, r.hour, r.gate))
    return records_sorted, warnings
