import unittest
from unittest.mock import patch

from app.services import aggregation


def day_records(date, values, *, gates=("front", "back"), partial_hour=None):
    records = []
    for hour, (ins, outs) in zip(range(9, 21), values):
        for index, gate in enumerate(gates):
            records.append({"date": date, "hour": hour, "gate": gate,
                            "in_count": ins // len(gates) + (ins % len(gates) if index == 0 else 0),
                            "out_count": None if outs is None else outs // len(gates) + (outs % len(gates) if index == 0 else 0),
                            "is_partial": hour == partial_hour, "is_closed_day": False})
    return records


class EstimatedPresentTests(unittest.TestCase):
    def test_cumulative_and_gate_sum(self):
        values = [(10, 0), (5, 3), (0, 8)] + [(0, 0)] * 9
        with patch.object(aggregation, "load_records", return_value=day_records("2026-09-28", values)):
            rows = aggregation._hourly_rows()
        self.assertEqual([r["estimated_present"] for r in rows[:3]], [10, 12, 4])

    def test_out_missing_partial_missing_gate_and_negative_block_remaining_hours(self):
        rows = day_records("2026-09-28", [(1, None)] + [(0, 0)] * 11)
        with patch.object(aggregation, "load_records", return_value=rows):
            result = aggregation._hourly_rows()
        self.assertEqual(result[0]["quality_status"], "missing_out")
        self.assertIsNone(result[1]["estimated_present"])

        with patch.object(aggregation, "load_records", return_value=day_records("2026-09-28", [(1, 0)] * 12, gates=("front",))):
            result = aggregation._hourly_rows()
        self.assertEqual(result[0]["quality_status"], "missing_gate")

        with patch.object(aggregation, "load_records", return_value=day_records("2026-09-28", [(0, 2)] + [(0, 0)] * 11)):
            result = aggregation._hourly_rows()
        self.assertEqual(result[0]["quality_status"], "negative_balance")
        self.assertIsNone(result[0]["estimated_present"])

    def test_weekday_same_hour_and_fallback(self):
        rows = []
        for date in ("2026-09-07", "2026-09-14", "2026-09-15"):
            rows.append({"date": date, "hour": 9, "estimated_present": 20, "quality_status": "valid"})
        with patch.object(aggregation, "BASELINE_WEEKS", 4):
            mean, count, basis = aggregation._baseline(rows, "2026-09-21", 9)
            self.assertEqual((mean, count, basis), (20.0, 2, "same_weekday_same_hour"))
            mean, count, basis = aggregation._baseline(rows, "2026-09-22", 9)
            self.assertEqual((mean, count, basis), (20.0, 3, "same_hour_fallback"))

    def test_date_reset_operating_hours_and_partial_data(self):
        first = day_records("2026-09-28", [(4, 0)] + [(0, 0)] * 11)
        second = day_records("2026-09-29", [(0, 0)] * 12)
        with patch.object(aggregation, "load_records", return_value=first + second):
            rows = aggregation._hourly_rows()
        self.assertEqual(rows[0]["estimated_present"], 4)
        next_date_first = next(r for r in rows if r["date"] == "2026-09-29" and r["hour"] == 9)
        self.assertEqual(next_date_first["estimated_present"], 0)
        self.assertEqual(list(aggregation._window("2026-09-28")), list(range(9, 21)))
        self.assertEqual(list(aggregation._window("2026-09-26")), list(range(9, 17)))

        with patch.object(aggregation, "load_records", return_value=day_records(
                "2026-09-28", [(1, 0)] * 12, partial_hour=11)):
            rows = aggregation._hourly_rows()
        hour_11 = next(r for r in rows if r["hour"] == 11)
        hour_12 = next(r for r in rows if r["hour"] == 12)
        self.assertEqual(hour_11["quality_status"], "partial")
        self.assertIsNone(hour_12["estimated_present"])


if __name__ == "__main__":
    unittest.main()
