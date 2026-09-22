"""records 스키마 + 6절 API 응답 스키마"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Gate = Literal["front", "back"]
Level = Literal["quiet", "normal", "busy"]
DataStatus = Literal["forecast", "partial", "actual", "closed"]


class RecordItem(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    day_of_week: str
    gate: Gate
    gate_name: str
    passage_id: str
    hour: int = Field(..., ge=8, le=23)
    in_count: int = Field(..., ge=0)
    out_count: Optional[int] = Field(None, ge=0)
    total_in: int = Field(..., ge=0)
    total_out: int = Field(..., ge=0)
    is_partial: bool
    source_file: str
    # 선택 품질 필드
    is_closed_day: Optional[bool] = None
    is_low_volume: bool = False
    quality_note: Optional[str] = None


class AdminUploadResult(BaseModel):
    accepted: bool
    record_count: int
    previous_backup: Optional[str] = None
    warnings: list[str] = []
    uploaded_at: str


# ---------- 6절 공개 API 응답 ----------
class OperatingWindow(BaseModel):
    open: str
    close: str


class OperatingHours(BaseModel):
    weekday: OperatingWindow
    weekend: OperatingWindow


class MetaResponse(BaseModel):
    library_name: str
    available_hours: list[int]
    operating_hours: OperatingHours
    levels: dict[str, str]


class CongestionNow(BaseModel):
    level: Optional[Level]
    label: str
    score: Optional[float]


class Recommendation(BaseModel):
    best_start_hour: int
    best_end_hour: int
    message: str


class TodayHourly(BaseModel):
    hour: int
    expected_visitors: int
    baseline_avg: Optional[float] = None
    difference_rate: Optional[float] = None
    level: Optional[Level] = None


class TodayCongestionResponse(BaseModel):
    date: str
    data_status: DataStatus
    reference_time: str
    congestion: CongestionNow
    recommendation: Recommendation
    hourly: list[TodayHourly]
    updated_at: str


class StatsHourly(BaseModel):
    hour: int
    in_count: int
    out_count: Optional[int] = None


class StatsResponse(BaseModel):
    date: str
    data_status: DataStatus
    total_in: int
    total_out: int
    hourly: list[StatsHourly]
