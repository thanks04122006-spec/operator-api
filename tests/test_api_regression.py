import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import aggregation
from app.core import admin_auth


def records_for(date="2026-09-28"):
    records = []
    for hour in range(9, 21):
        for gate in ("front", "back"):
            records.append({
                "date": date, "day_of_week": "Mon", "gate": gate,
                "gate_name": "자료실.정문" if gate == "front" else "자료실.후문",
                "passage_id": "front-id" if gate == "front" else "back-id",
                "hour": hour, "in_count": 1 if hour == 9 and gate == "front" else 0,
                "out_count": 0, "total_in": 1, "total_out": 0,
                "is_partial": False, "source_file": "fixture.json",
            })
    return records


class ApiRegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_existing_public_routes_and_stats_raw_counts(self):
        with patch.object(aggregation, "load_records", return_value=records_for()):
            meta = self.client.get("/api/v1/meta")
            self.assertEqual(meta.status_code, 200)
            self.assertIn("operating_hours", meta.json())

            stats = self.client.get("/api/v1/stats", params={"date": "2026-09-28"})
            self.assertEqual(stats.status_code, 200)
            payload = stats.json()
            self.assertEqual(payload["total_in"], 1)
            self.assertEqual(payload["total_out"], 0)
            first = next(row for row in payload["hourly"] if row["hour"] == 9)
            self.assertEqual(first["estimated_present"], 1)
            self.assertEqual(first["in_count"], 1)

            congestion = self.client.get("/api/v1/congestion/today")
            self.assertEqual(congestion.status_code, 200)
            for hour in congestion.json()["hourly"]:
                self.assertIn("estimated_present", hour)
                self.assertIn("quality_status", hour)

    def test_records_upload_contract(self):
        admin_auth.ADMIN_UPLOAD_TOKEN = "test-token"
        try:
            with patch("app.routers.admin.records_store.atomic_replace", return_value="backup.json") as replace, \
                 patch("app.routers.admin.upload_log.log_upload"):
                response = self.client.post("/api/v1/admin/records",
                                            headers={"Authorization": "Bearer test-token"},
                                            json=records_for())
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["accepted"])
            replace.assert_called_once()
        finally:
            admin_auth.ADMIN_UPLOAD_TOKEN = None


if __name__ == "__main__":
    unittest.main()
