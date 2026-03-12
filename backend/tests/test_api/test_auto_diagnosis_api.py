"""
API-level tests for auto-diagnosis routes.

Covers:
- GET  /diagnosis/auto/status
- GET  /diagnosis/auto-results
- POST /diagnosis/auto/start
- POST /diagnosis/auto/stop  (new contract: dropped_queue + queue-clear semantics)
- POST /diagnosis/auto/reset-cooldowns
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.api.deps import get_auto_diagnosis_service
from app.main import app
from app.services.auto_diagnosis_service import AutoDiagnosisService

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_service() -> AutoDiagnosisService:
    return AutoDiagnosisService()


def _override(svc: AutoDiagnosisService):
    """Return a FastAPI dependency override that yields the given service."""
    def _dep():
        return svc
    return _dep


# ── Status endpoint ───────────────────────────────────────────────────────────

class TestAutoStatus:

    def test_status_shape_when_idle(self, client):
        body = client.get("/diagnosis/auto/status").json()
        assert body["running"] is False
        assert isinstance(body["pending_queue"], list)
        assert isinstance(body["unit_cooldowns"], dict)
        assert isinstance(body["completed_count"], int)
        assert body["epoch_phase"] in ("NORMAL", "PRE_FAULT", "FAULT", "COOL_DOWN")

    def test_status_current_is_null_when_idle(self, client):
        body = client.get("/diagnosis/auto/status").json()
        assert body["current"] is None


# ── Results endpoint ──────────────────────────────────────────────────────────

class TestAutoResults:

    def test_results_returns_list(self, client):
        resp = client.get("/diagnosis/auto-results")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Start endpoint ────────────────────────────────────────────────────────────

class TestAutoStart:
    # We mock svc.start() to avoid spawning real asyncio tasks in the test
    # client's event loop.  The service unit tests in test_auto_diagnosis_service.py
    # already verify the task-creation behaviour end-to-end.

    def test_start_returns_ok_when_not_running(self, client):
        svc = _make_service()
        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            with patch.object(svc, "start", new_callable=AsyncMock, return_value=False):
                resp = client.post("/diagnosis/auto/start")
                assert resp.status_code == 200
                body = resp.json()
                assert body["ok"] is True
                assert body["already_running"] is False
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)

    def test_start_returns_already_running_when_running(self, client):
        svc = _make_service()
        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            with patch.object(svc, "start", new_callable=AsyncMock, return_value=True):
                resp = client.post("/diagnosis/auto/start")
                assert resp.json()["already_running"] is True
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)


# ── Stop endpoint — new contract ──────────────────────────────────────────────

class TestAutoStop:

    def test_stop_when_idle_returns_ok_with_empty_dropped(self, client):
        svc = _make_service()
        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            resp = client.post("/diagnosis/auto/stop")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["polling_was_running"] is False
            assert body["dropped_queue"] == []
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)

    def test_stop_clears_queue_and_returns_dropped_snapshot(self, client):
        """
        Core new contract: queued items must be returned in dropped_queue and
        must no longer be present in _pending after the call.
        """
        from mcp_servers.fault_aggregator import FaultSummary
        svc = _make_service()
        svc.enqueue(FaultSummary(
            unit_id="#1机", fault_types=["vibration_swing"],
            anomaly_points=[], symptom_text="振动偏高", sensor_reports=[],
        ))
        svc.enqueue(FaultSummary(
            unit_id="#3机", fault_types=["bearing_temp_cooling"],
            anomaly_points=[], symptom_text="轴承温升", sensor_reports=[],
        ))
        assert len(svc._pending) == 2

        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            resp = client.post("/diagnosis/auto/stop")
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert len(body["dropped_queue"]) == 2
            units = {d["unit_id"] for d in body["dropped_queue"]}
            assert units == {"#1机", "#3机"}
            # Backend queue must be empty — items won't be processed
            assert len(svc._pending) == 0
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)

    def test_stop_does_not_clear_current_in_flight_diagnosis(self, client):
        """
        Items already in _current (being diagnosed) must NOT appear in
        dropped_queue — the in-flight diagnosis is allowed to finish.
        """
        from datetime import UTC, datetime

        from app.services.auto_diagnosis_service import CurrentDiagnosisState

        svc = _make_service()
        # Simulate an in-flight diagnosis
        svc._current = CurrentDiagnosisState(
            session_id="auto-test-123",
            unit_id="#2机",
            fault_types=["governor_oil_pressure"],
            phase="reasoning",
            stream_preview="",
            sensor_data=[],
            started_at=datetime.now(tz=UTC),
        )

        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            resp = client.post("/diagnosis/auto/stop")
            body = resp.json()
            # In-flight item is NOT in dropped_queue
            assert body["dropped_queue"] == []
            # _current is still set — worker will finish it
            assert svc._current is not None
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)
            svc._current = None

    def test_dropped_queue_items_have_required_fields(self, client):
        from mcp_servers.fault_aggregator import FaultSummary
        svc = _make_service()
        svc.enqueue(FaultSummary(
            unit_id="#4机", fault_types=["vibration_swing"],
            anomaly_points=[], symptom_text="摆度超限", sensor_reports=[],
        ))

        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            body = client.post("/diagnosis/auto/stop").json()
            item = body["dropped_queue"][0]
            assert "unit_id" in item
            assert "fault_types" in item
            assert "symptom_preview" in item
            assert "queued_at" in item
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)


# ── Reset-cooldowns endpoint ──────────────────────────────────────────────────

class TestResetCooldowns:

    def test_reset_cooldowns_returns_ok(self, client):
        resp = client.post("/diagnosis/auto/reset-cooldowns")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_reset_cooldowns_clears_active_cooldowns(self, client):
        """After a reset, all units must report 0 cooldown remaining."""
        import time
        svc = _make_service()
        # Simulate a recently-diagnosed unit by writing a recent trigger time
        svc._agg._last_triggered["#1机"] = time.monotonic()  # just triggered
        assert svc._agg.cooldown_remaining("#1机") > 0

        app.dependency_overrides[get_auto_diagnosis_service] = _override(svc)
        try:
            resp = client.post("/diagnosis/auto/reset-cooldowns")
            assert resp.json()["ok"] is True
            assert svc._agg.cooldown_remaining("#1机") == 0
        finally:
            app.dependency_overrides.pop(get_auto_diagnosis_service, None)
