"""4~6절: 시간대별 집계 + baseline + 혼잡도(congestion.midrank_score) + 휴관일 판정"""
from __future__ import annotations

from datetime import datetime, timedelta
from collections import defaultdict

from app.core.config import BASELINE_WEEKS
from app.services import congestion as congestion_calc
from app.services.records_store import load_records

# 공식 휴관일 (기존 records에 is_closed_day가 없는 날짜도 커버하고 싶으면 여기에 추가)
CLOSED_DATES: set[str] = set()


def _hourly_rows() -> list[dict]:
    """records.json을 date+hour 단위로 합산 (정문+후문)."""
    records = load_records()
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in records:
        grouped[(r["date"], r["hour"])].append(r)

    rows = []
    for (date_str, hour), items in grouped.items():
        in_count = sum(r["in_count"] for r in items)
        out_values = [r.get("out_count") for r in items]
        out_count = None if any(v is None for v in out_values) else sum(out_values)
        is_partial = any(r.get("is_partial") for r in items) or {r["gate"] for r in items} != {"front", "back"}
        is_closed = any(r.get("is_closed_day") for r in items)
        rows.append(
            {
                "date": date_str,
                "hour": hour,
                "in_count": in_count,
                "out_count": out_count,
                "visit_count": in_count,
                "is_partial": is_partial,
                "is_closed_day": is_closed,
            }
        )
    return rows


def is_closed_date(date_str: str, rows: list[dict] | None = None) -> bool:
    if date_str in CLOSED_DATES:
        return True
    rows = rows if rows is not None else _hourly_rows()
    day_rows = [r for r in rows if r["date"] == date_str]
    return bool(day_rows) and all(r["is_closed_day"] for r in day_rows)


def _baseline(rows: list[dict], target_date: str, hour: int) -> float | None:
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    values = []
    for w in range(1, BASELINE_WEEKS + 1):
        prev_date = (target_dt - timedelta(weeks=w)).strftime("%Y-%m-%d")
        match = next((r for r in rows if r["date"] == prev_date and r["hour"] == hour), None)
        if match:
            values.append(float(match["visit_count"]))
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _difference_rate(actual: float, baseline: float | None) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return round((actual - baseline) / baseline * 100, 1)


def _historical_distribution(rows: list[dict], hour: int, exclude_date: str | None = None) -> list[float]:
    return [float(r["visit_count"]) for r in rows if r["hour"] == hour and r["date"] != exclude_date]


def stats_for_date(date_str: str) -> dict | None:
    """GET /api/v1/stats?date= 용 집계. 데이터가 전혀 없으면 None."""
    rows = _hourly_rows()

    if is_closed_date(date_str, rows):
        return {
            "date": date_str,
            "data_status": "closed",
            "total_in": 0,
            "total_out": 0,
            "hourly": [],
        }

    day_rows = sorted([r for r in rows if r["date"] == date_str], key=lambda r: r["hour"])
    if not day_rows:
        return None

    total_in = sum(r["in_count"] for r in day_rows)
    out_values = [r["out_count"] for r in day_rows]
    total_out = 0 if any(v is None for v in out_values) else sum(out_values)
    is_partial = any(r["is_partial"] for r in day_rows) or len(day_rows) < 16

    return {
        "date": date_str,
        "data_status": "partial" if is_partial else "actual",
        "total_in": total_in,
        "total_out": total_out,
        "hourly": [{"hour": r["hour"], "in_count": r["in_count"], "out_count": r["out_count"]} for r in day_rows],
    }


def today_forecast() -> dict:
    """GET /api/v1/congestion/today 용 예측."""
    today = datetime.now().strftime("%Y-%m-%d")
    current_hour = datetime.now().hour
    rows = _hourly_rows()

    if is_closed_date(today, rows):
        return {
            "date": today,
            "data_status": "closed",
            "reference_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "congestion": {"level": None, "label": "휴관일", "score": None},
            "recommendation": {"best_start_hour": 0, "best_end_hour": 0, "message": "오늘은 휴관일입니다."},
            "hourly": [],
            "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        }

    today_rows = {r["hour"]: r for r in rows if r["date"] == today}

    hourly_result = []
    for hour in range(8, 24):
        baseline = _baseline(rows, today, hour)
        if hour in today_rows:
            expected = int(today_rows[hour]["visit_count"])
        elif baseline is not None:
            expected = int(round(baseline))
        else:
            expected = 0

        diff = _difference_rate(expected, baseline)
        dist = _historical_distribution(rows, hour, exclude_date=today)
        if dist:
            score, level = congestion_calc.midrank_score(expected, dist)
        else:
            score, level = None, None

        hourly_result.append(
            {"hour": hour, "expected_visitors": expected, "baseline_avg": baseline, "difference_rate": diff, "level": level}
        )

    current = next((h for h in hourly_result if h["hour"] == current_hour), hourly_result[0])
    dist_now = _historical_distribution(rows, current["hour"], exclude_date=today)
    if dist_now:
        score_now, level_now = congestion_calc.midrank_score(current["expected_visitors"], dist_now)
    else:
        score_now, level_now = None, None

    candidates = [h for h in hourly_result if h["level"] in (None, "quiet", "normal")] or hourly_result
    best_hour = min(candidates, key=lambda h: h["expected_visitors"])["hour"]
    best_start, best_end = best_hour, min(best_hour + 2, 23 + 1)

    return {
        "date": today,
        "data_status": "forecast" if not today_rows else "partial",
        "reference_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "congestion": {
            "level": level_now,
            "label": congestion_calc.label(level_now) if level_now else "예측 자료 없음",
            "score": score_now,
        },
        "recommendation": {
            "best_start_hour": best_start,
            "best_end_hour": best_end,
            "message": f"오전 {best_start}시~{best_end}시 방문을 추천합니다."
            if best_start < 12
            else f"{best_start}시~{best_end}시 방문을 추천합니다.",
        },
        "hourly": hourly_result,
        "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    }
