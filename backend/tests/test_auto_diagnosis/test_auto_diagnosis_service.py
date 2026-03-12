"""
Unit tests for AutoDiagnosisService.

契约：
1. start() → stop() → start() 不产生第二个 worker（单 worker 串行保证）
2. stop() 后 running=False，_worker_task 仍存活
3. start() 幂等：polling 已运行时返回 already=True，不新建任何 task
4. pending_queue[].queued_at 在入队时固定，跨多次 get_status() 调用不变
5. _current 在 _run_one() 结束（成功或异常）后清为 None
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import patch

import pytest

from mcp_servers.fault_aggregator import FaultSummary

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_summary(unit_id: str = "#1机") -> FaultSummary:
    return FaultSummary(
        unit_id=unit_id,
        fault_types=["vibration_swing"],
        anomaly_points=[],
        symptom_text="水导摆度升高",
        sensor_reports=[],
    )


def _make_service():
    """
    Fresh AutoDiagnosisService with an isolated DiagnosisStore.
    Patches get_store() at construction so tests do not touch the module singleton.
    """
    from app.services.auto_diagnosis_service import AutoDiagnosisService
    from app.store.diagnosis_store import DiagnosisStore

    fresh_store = DiagnosisStore(max_size=5)
    with patch("app.services.auto_diagnosis_service.get_store", return_value=fresh_store):
        return AutoDiagnosisService()


async def _infinite_coroutine(*args, **kwargs):
    """Stand-in for FaultAggregator.run_polling_loop — blocks until cancelled."""
    await asyncio.sleep(9999)


# ── start / stop / start state machine ───────────────────────────────────────

class TestStartStopStateMachine:

    @pytest.mark.asyncio
    async def test_start_creates_both_tasks(self):
        svc = _make_service()
        with patch.object(svc._agg, "run_polling_loop", side_effect=_infinite_coroutine):
            await svc.start()
            try:
                assert svc.running
                assert svc._worker_alive
                assert svc._polling_task is not None
                assert svc._worker_task is not None
            finally:
                await svc.stop()
                await svc.drain()

    @pytest.mark.asyncio
    async def test_start_returns_false_on_first_call(self):
        svc = _make_service()
        with patch.object(svc._agg, "run_polling_loop", side_effect=_infinite_coroutine):
            already = await svc.start()
            try:
                assert already is False
            finally:
                await svc.stop()
                await svc.drain()

    @pytest.mark.asyncio
    async def test_start_is_idempotent_when_already_running(self):
        """Calling start() twice returns already=True on the second call."""
        svc = _make_service()
        with patch.object(svc._agg, "run_polling_loop", side_effect=_infinite_coroutine):
            await svc.start()
            try:
                already = await svc.start()
                assert already is True
            finally:
                await svc.stop()
                await svc.drain()

    @pytest.mark.asyncio
    async def test_stop_halts_polling_keeps_worker_alive(self):
        svc = _make_service()
        with patch.object(svc._agg, "run_polling_loop", side_effect=_infinite_coroutine):
            await svc.start()
            worker_before_stop = svc._worker_task

            was_running = await svc.stop()

            assert was_running is True
            assert not svc.running             # polling is gone
            assert svc._worker_alive           # worker still running
            assert svc._worker_task is worker_before_stop

            await svc.drain()

    @pytest.mark.asyncio
    async def test_stop_then_start_reuses_existing_worker(self):
        """
        P1 fix: stop() → start() must not spawn a second worker.
        The _worker_task identity must be unchanged after the second start().
        """
        svc = _make_service()
        with patch.object(svc._agg, "run_polling_loop", side_effect=_infinite_coroutine):
            # First start
            await svc.start()
            worker_after_first_start = svc._worker_task
            assert worker_after_first_start is not None

            # Stop polling — worker survives
            await svc.stop()
            assert not svc.running
            assert svc._worker_task is worker_after_first_start

            # Second start — worker is still alive, must NOT create a new task
            await svc.start()
            assert svc._worker_task is worker_after_first_start, (
                "stop() → start() spawned a second worker task, violating single-worker guarantee"
            )
            assert svc.running   # polling is back

            await svc.stop()
            await svc.drain()

    @pytest.mark.asyncio
    async def test_multiple_stop_start_cycles_never_accumulate_workers(self):
        """Three stop/start cycles must leave exactly one live worker at all times."""
        svc = _make_service()
        with patch.object(svc._agg, "run_polling_loop", side_effect=_infinite_coroutine):
            await svc.start()
            original_worker = svc._worker_task

            for cycle in range(3):
                await svc.stop()
                await svc.start()
                assert svc._worker_task is original_worker, (
                    f"cycle {cycle + 1}: worker task identity changed — second worker spawned"
                )

            await svc.stop()
            await svc.drain()

    @pytest.mark.asyncio
    async def test_stop_returns_false_when_not_running(self):
        svc = _make_service()
        was_running = await svc.stop()
        assert was_running is False


# ── pending_queue.queued_at stability ────────────────────────────────────────

class TestQueuedAtStability:

    def test_queued_at_is_stable_across_multiple_get_status_calls(self):
        """
        P2 fix: queued_at must be the enqueue time, not datetime.now() at query time.
        The value must be identical across consecutive get_status() calls.
        """
        svc = _make_service()
        svc.enqueue(_make_summary())

        status1 = svc.get_status()
        status2 = svc.get_status()

        q1 = status1["pending_queue"]
        q2 = status2["pending_queue"]

        assert len(q1) == 1
        assert len(q2) == 1
        assert q1[0]["queued_at"] == q2[0]["queued_at"], (
            "queued_at changed between consecutive get_status() calls — "
            "it must be captured at enqueue time, not regenerated on each poll"
        )

    def test_queued_at_is_iso_format_with_timezone(self):
        """queued_at must be a timezone-aware ISO-8601 string."""
        svc = _make_service()
        svc.enqueue(_make_summary())

        status = svc.get_status()
        queued_at = status["pending_queue"][0]["queued_at"]

        parsed = datetime.fromisoformat(queued_at)
        assert parsed.tzinfo is not None, "queued_at must include timezone info"

    def test_queued_at_captured_before_get_status_call(self):
        """queued_at must not be later than the first get_status() call."""
        svc = _make_service()

        before_enqueue = datetime.now().astimezone()
        svc.enqueue(_make_summary())
        after_enqueue = datetime.now().astimezone()

        status = svc.get_status()
        queued_at = datetime.fromisoformat(status["pending_queue"][0]["queued_at"])

        assert before_enqueue <= queued_at <= after_enqueue, (
            f"queued_at={queued_at} is outside the [{before_enqueue}, {after_enqueue}] window"
        )

    def test_two_enqueues_get_distinct_queued_at(self):
        """Two separate enqueue() calls must produce different queued_at values."""
        svc = _make_service()
        svc.enqueue(_make_summary("#1机"))
        time.sleep(0.005)  # ensure a measurable time gap
        svc.enqueue(_make_summary("#2机"))

        status = svc.get_status()
        q = status["pending_queue"]  # newest first (LIFO display order)
        assert len(q) == 2
        assert q[0]["queued_at"] != q[1]["queued_at"]


# ── _current lifecycle ────────────────────────────────────────────────────────

class TestCurrentLifecycle:

    @pytest.mark.asyncio
    async def test_current_is_none_after_run_one_succeeds(self):
        """
        P2 fix: _current must be None after _run_one() completes successfully,
        so get_status() returns current=null instead of a stale record.
        """
        from app.store.diagnosis_store import AutoDiagnosisRecord

        svc = _make_service()
        summary = _make_summary()

        async def _mock_streaming(summary, store, session_id, **kwargs):
            rec = AutoDiagnosisRecord(
                session_id=session_id,
                unit_id=summary.unit_id,
                fault_types=summary.fault_types,
                symptom_text=summary.symptom_text,
            )
            store.push(rec)
            return rec

        with patch(
            "app.agents.auto_diagnosis.run_auto_diagnosis_streaming",
            side_effect=_mock_streaming,
        ):
            await svc._run_one(summary)

        assert svc._current is None
        assert svc.get_status()["current"] is None

    @pytest.mark.asyncio
    async def test_current_is_none_after_run_one_raises(self):
        """_current must also be cleared when the runner raises an exception."""
        svc = _make_service()
        summary = _make_summary()

        async def _failing_streaming(**kwargs):
            raise RuntimeError("graph unavailable")

        with patch(
            "app.agents.auto_diagnosis.run_auto_diagnosis_streaming",
            side_effect=_failing_streaming,
        ):
            # _run_one must not propagate the exception
            await svc._run_one(summary)

        assert svc._current is None
        assert svc.get_status()["current"] is None

    @pytest.mark.asyncio
    async def test_current_is_set_during_run_one(self):
        """_current must be non-None while _run_one() is executing."""
        svc = _make_service()
        summary = _make_summary("#3机")
        observed_during: list[object] = []

        async def _mock_streaming(summary, store, session_id, on_phase=None, **kwargs):
            # Snapshot _current mid-run
            observed_during.append(svc._current)
            from app.store.diagnosis_store import AutoDiagnosisRecord
            rec = AutoDiagnosisRecord(
                session_id=session_id,
                unit_id=summary.unit_id,
                fault_types=summary.fault_types,
                symptom_text=summary.symptom_text,
            )
            store.push(rec)
            return rec

        with patch(
            "app.agents.auto_diagnosis.run_auto_diagnosis_streaming",
            side_effect=_mock_streaming,
        ):
            await svc._run_one(summary)

        assert len(observed_during) == 1
        mid_current = observed_during[0]
        assert mid_current is not None
        assert mid_current.unit_id == "#3机"  # type: ignore[union-attr]
