"""
T04 혼잡도 판정 기준 (ADE-8)

기준: 과거 유효한 추정 체류 인원 분포에서의 midrank 백분위 점수
  - 35 이하 → 여유 (quiet)
  - 36 ~ 70 → 보통 (normal)
  - 71 이상  → 혼잡 (busy)

추정 체류 인원은 정확한 실시간 인원이나 좌석 점유율이 아닙니다.
분포 전체가 동일한 값이면 50.0(보통)으로 처리합니다.
"""
from __future__ import annotations

THRESHOLDS: dict[str, float] = {
    "quiet": 35.0,
    "normal": 70.0,
}

LABELS: dict[str, str] = {"quiet": "여유", "normal": "보통", "busy": "혼잡"}

DESCRIPTIONS: dict[str, str] = {
    "quiet": "과거 유효 자료의 추정 체류 인원보다 적을 것으로 예상됩니다.",
    "normal": "과거 유효 자료와 비슷한 추정 체류 인원이 예상됩니다.",
    "busy": "과거 유효 자료보다 추정 체류 인원이 많을 것으로 예상됩니다.",
}


def classify(score: float) -> str:
    if score <= THRESHOLDS["quiet"]:
        return "quiet"
    if score <= THRESHOLDS["normal"]:
        return "normal"
    return "busy"


def midrank_score(value: float | int, distribution: list) -> tuple[float, str]:
    """
    Raises:
        ValueError: distribution이 비어 있을 때
    """
    if not distribution:
        raise ValueError("분포가 비어 있습니다.")
    n = len(distribution)
    below = sum(v < value for v in distribution)
    equal = sum(v == value for v in distribution)
    score = round(100.0 * (below + 0.5 * equal) / n, 1)
    return score, classify(score)


def label(level: str) -> str:
    return LABELS.get(level, "알 수 없음")


def description(level: str) -> str:
    return DESCRIPTIONS.get(level, "")
