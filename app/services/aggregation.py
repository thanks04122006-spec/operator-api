"""시간대 집계, 추정 체류 인원, 기준 예측 및 혼잡도."""
from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls, datetime, timedelta

from app.core.config import BASELINE_WEEKS, OPERATING_HOURS
from app.services import congestion as congestion_calc
from app.services.records_store import load_records

CLOSED_DATES: set[str] = set()
GATES = {"front", "back"}
MIN_WEEKDAY_SAMPLES = 2


def _window(date_str: str) -> range:
    day = date_cls.fromisoformat(date_str)
    spec = OPERATING_HOURS["weekend" if day.weekday() >= 5 else "weekday"]
    opening = int(spec["open"].split(":")[0])
    closing = int(spec["close"].split(":")[0])
    return range(opening, closing)


def _hourly_rows() -> list[dict]:
    """정문+후문 원본을 합산하고, 품질 조건이 확인된 날짜만 누적 계산한다."""
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for record in load_records():
        grouped[(record["date"], record["hour"])].append(record)

    rows: list[dict] = []
    by_date: dict[str, list[dict]] = defaultdict(list)
    for (date_str, hour), items in grouped.items():
        ins = sum(r["in_count"] for r in items)
        outs = [r.get("out_count") for r in items]
        gates = {r["gate"] for r in items}
        row = {
            "date": date_str, "hour": hour, "in_count": ins,
            "out_count": None if any(v is None for v in outs) else sum(outs),
            "gates": gates,
            "is_partial": any(r.get("is_partial", False) for r in items),
            "is_closed_day": any(r.get("is_closed_day") for r in items),
            "quality_status": "valid", "estimated_present": None,
        }
        rows.append(row)
        by_date[date_str].append(row)

    for date_str, day_rows in by_date.items():
        indexed = {r["hour"]: r for r in day_rows}
        balance = 0
        invalid = False
        for hour in _window(date_str):
            row = indexed.get(hour)
            if row is None:
                invalid = True
                continue
            if invalid:
                row["quality_status"] = "insufficient_data"
                continue
            if row["gates"] != GATES:
                row["quality_status"] = "missing_gate"
                invalid = True
            elif row["is_partial"]:
                row["quality_status"] = "partial"
                invalid = True
            elif row["out_count"] is None:
                row["quality_status"] = "missing_out"
                invalid = True
            else:
                next_balance = balance + row["in_count"] - row["out_count"]
                if next_balance < 0:
                    row["quality_status"] = "negative_balance"
                    invalid = True
                else:
                    balance = next_balance
                    row["estimated_present"] = balance
        # 운영시간 외 행은 통계에서 원본만 유지하며 추정에는 포함하지 않는다.
    return sorted(rows, key=lambda r: (r["date"], r["hour"]))


def is_closed_date(date_str: str, rows: list[dict] | None = None) -> bool:
    if date_str in CLOSED_DATES:
        return True
    rows = rows if rows is not None else _hourly_rows()
    day_rows = [r for r in rows if r["date"] == date_str]
    return bool(day_rows) and all(r["is_closed_day"] for r in day_rows)


def _recent_same_hour(rows: list[dict], target_date: str, hour: int) -> list[dict]:
    target = date_cls.fromisoformat(target_date)
    lower = target - timedelta(weeks=BASELINE_WEEKS)
    return [r for r in rows if lower <= date_cls.fromisoformat(r["date"]) < target
            and r["hour"] == hour and r["estimated_present"] is not None]


def _baseline(rows: list[dict], target_date: str, hour: int) -> tuple[float | None, int, str]:
    candidates = _recent_same_hour(rows, target_date, hour)
    weekday = date_cls.fromisoformat(target_date).weekday()
    same_weekday = [r for r in candidates if date_cls.fromisoformat(r["date"]).weekday() == weekday]
    if len(same_weekday) >= MIN_WEEKDAY_SAMPLES:
        sample, basis = same_weekday, "same_weekday_same_hour"
    elif candidates:
        sample, basis = candidates, "same_hour_fallback"
    else:
        return None, 0, "insufficient_samples"
    return round(sum(r["estimated_present"] for r in sample) / len(sample), 2), len(sample), basis


def _historical_distribution(rows: list[dict], hour: int, exclude_date: str | None = None) -> list[float]:
    return [float(r["estimated_present"]) for r in rows
            if r["hour"] == hour and r["date"] != exclude_date and r["estimated_present"] is not None]


def _difference_rate(actual: float, baseline: float | None) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return round((actual - baseline) / baseline * 100, 1)


def stats_for_date(date_str: str) -> dict | None:
    rows = _hourly_rows()
    if is_closed_date(date_str, rows):
        return {"date": date_str, "data_status": "closed", "total_in": 0,
                "total_out": 0, "hourly": []}
    day_rows = sorted((r for r in rows if r["date"] == date_str), key=lambda r: r["hour"])
    if not day_rows:
        return None
    total_in = sum(r["in_count"] for r in day_rows)
    total_out = None if any(r["out_count"] is None for r in day_rows) else sum(r["out_count"] for r in day_rows)
    window = _window(date_str)
    qualities = {r["quality_status"] for r in day_rows if r["hour"] in window}
    observed_hours = {r["hour"] for r in day_rows}
    status = "actual" if qualities <= {"valid"} and set(window) <= observed_hours else "insufficient_data"
    hourly = []
    for r in day_rows:
        item = {"hour": r["hour"], "in_count": r["in_count"], "out_count": r["out_count"]}
        if r["hour"] in _window(date_str):
            item.update(estimated_present=r["estimated_present"], quality_status=r["quality_status"])
        hourly.append(item)
    return {"date": date_str, "data_status": status, "total_in": total_in,
            "total_out": total_out, "hourly": hourly}


def today_forecast() -> dict:
    now = datetime.now()
    today, current_hour = now.strftime("%Y-%m-%d"), now.hour
    rows = _hourly_rows()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    if is_closed_date(today, rows):
        return {"date": today, "data_status": "closed", "reference_time": timestamp,
                "congestion": {"level": None, "label": "휴관일", "score": None},
                "recommendation": {"best_start_hour": 0, "best_end_hour": 0, "message": "오늘은 휴관일입니다."},
                "hourly": [], "updated_at": timestamp}

    today_by_hour = {r["hour"]: r for r in rows if r["date"] == today}
    hourly_result = []
    window_hours = list(_window(today))
    for hour in _window(today):
        current = today_by_hour.get(hour)
        baseline, sample_count, basis = _baseline(rows, today, hour)
        actual_estimate = current["estimated_present"] if current else None
        if actual_estimate is not None:
            estimate = actual_estimate
        elif current is not None:
            estimate = None
        else:
            prior_hours = [h for h in window_hours if h < hour]
            prior_complete = all(
                h in today_by_hour and today_by_hour[h]["estimated_present"] is not None
                for h in prior_hours
            )
            # 유효한 당일 누적 이후의 아직 도래하지 않은 시간은 기준 예측을 쓴다.
            # 지나간 시간의 누락/불량은 뒤 시간대의 기준값으로 덮지 않는다.
            estimate = round(baseline) if (not today_by_hour or (hour > current_hour and prior_complete)) and baseline is not None else None
        quality = current["quality_status"] if current else (
            "forecast" if estimate is not None and today_by_hour else
            "insufficient_data" if today_by_hour and estimate is None else
            "forecast" if baseline is not None else "insufficient_samples"
        )
        source = "observed_cumulative" if actual_estimate is not None else basis
        dist = _historical_distribution(rows, hour, exclude_date=today)
        if estimate is not None and dist:
            score, level = congestion_calc.midrank_score(estimate, dist)
        else:
            score, level = None, None
        hourly_result.append({"hour": hour, "expected_visitors": estimate,
                              "estimated_present": estimate, "baseline_avg": baseline,
                              "difference_rate": _difference_rate(estimate, baseline) if estimate is not None else None,
                              "level": level, "score": score, "calculation_basis": source,
                              "sample_count": sample_count, "quality_status": quality})

    current_row = next((h for h in hourly_result if h["hour"] == current_hour), None)
    if current_row is None:
        current_row = next((h for h in hourly_result if h["hour"] > current_hour), hourly_result[-1] if hourly_result else None)
    level = current_row["level"] if current_row else None
    score = current_row["score"] if current_row else None
    recommendation_candidates = [h for h in hourly_result if h["estimated_present"] is not None and h["level"] in ("quiet", "normal")]
    if not recommendation_candidates:
        recommendation_candidates = [h for h in hourly_result if h["estimated_present"] is not None]
    best_hour = min(recommendation_candidates, key=lambda h: h["estimated_present"])["hour"] if recommendation_candidates else 0
    best_end = min(best_hour + 2, _window(today).stop) if best_hour else 0
    return {"date": today, "data_status": "partial" if today_by_hour else "forecast",
            "reference_time": timestamp,
            "congestion": {"level": level, "label": congestion_calc.label(level) if level else "자료 부족/추정 불가", "score": score},
            "recommendation": {"best_start_hour": best_hour, "best_end_hour": best_end,
                               "message": f"{best_hour}시~{best_end}시 방문을 추천합니다." if best_hour else "자료 부족으로 추천할 수 없습니다."},
            "hourly": hourly_result, "updated_at": timestamp}
