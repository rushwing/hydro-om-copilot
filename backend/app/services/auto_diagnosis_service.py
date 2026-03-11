"""
AutoDiagnosisService — LIFO fault queue + background worker + live status tracking.

Manages:
- FaultAggregator polling loop (start/stop)
- LIFO deque of pending FaultSummary items
- A single worker coroutine that runs auto-diagnosis one at a time
- CurrentDiagnosisState for live UI display
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.config import settings
from app.store.diagnosis_store import get_store
from mcp_servers.fault_aggregator import FaultAggregator, FaultSummary

_logger = logging.getLogger("app.services.auto_diagnosis_service")

_MONITORED_UNITS = ["#1机", "#2机", "#3机", "#4机"]


@dataclass
class CurrentDiagnosisState:
    session_id: str
    unit_id: str
    fault_types: list[str]
    phase: str               # sensor_reader | symptom_parser | retrieval | reasoning | report_gen | done | error  # noqa: E501
    stream_preview: str      # last 500 chars of accumulated tokens
    sensor_data: list[dict]
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


# Internal queue entry — bundles FaultSummary with its actual enqueue timestamp
@dataclass
class _QueueEntry:
    summary: FaultSummary
    queued_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


class AutoDiagnosisService:
    def __init__(self) -> None:
        self._pending: deque[_QueueEntry] = deque(maxlen=settings.fault_queue_max)
        self._wake: asyncio.Event = asyncio.Event()
        self._polling_task: asyncio.Task | None = None
        self._worker_task: asyncio.Task | None = None
        self._current: CurrentDiagnosisState | None = None
        self._agg = FaultAggregator(cooldown_s=settings.diagnosis_cooldown_s)
        self._store = get_store()
        self._completed_count: int = 0

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        """True if polling loop is active."""
        return self._polling_task is not None and not self._polling_task.done()

    @property
    def _worker_alive(self) -> bool:
        return self._worker_task is not None and not self._worker_task.done()

    async def start(self) -> bool:
        """Start polling + worker. Returns True if already running (idempotent).

        Worker is only created when none is currently alive, so stop() → start()
        cycles reuse the surviving worker instead of spawning a second one.
        """
        already = self.running
        if not already:
            # Only create a new worker if the previous one has exited
            if not self._worker_alive:
                self._worker_task = asyncio.create_task(
                    self._worker(), name="auto-diagnosis-worker"
                )
            self._polling_task = asyncio.create_task(
                self._agg.run_polling_loop(
                    _MONITORED_UNITS,
                    interval_s=settings.sensor_poll_interval_s,
                    on_fault=self.enqueue,
                ),
                name="auto-diagnosis-polling",
            )
            _logger.info(
                "AutoDiagnosisService started | poll_interval=%ds cooldown=%ds",
                settings.sensor_poll_interval_s,
                settings.diagnosis_cooldown_s,
            )
        return already

    async def stop(self) -> bool:
        """Stop polling only; worker continues until current diagnosis finishes."""
        was_running = self.running
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
            _logger.info("AutoDiagnosisService polling stopped (worker continues)")
        return was_running

    def enqueue(self, summary: FaultSummary) -> None:
        """Add a FaultSummary to the LIFO queue, recording the actual enqueue time."""
        entry = _QueueEntry(summary=summary)
        self._pending.append(entry)
        self._wake.set()
        _logger.info(
            "fault enqueued | unit=%s types=%s | queue_len=%d",
            summary.unit_id,
            summary.fault_types,
            len(self._pending),
        )

    def get_status(self) -> dict:
        """Return serializable status dict for the /status endpoint."""
        unit_cooldowns = {
            uid: self._agg.cooldown_remaining(uid)
            for uid in _MONITORED_UNITS
        }

        # queued_at is captured at enqueue time — stable across polls
        pending_queue = [
            {
                "unit_id": entry.summary.unit_id,
                "fault_types": entry.summary.fault_types,
                "symptom_preview": entry.summary.symptom_text[:100],
                "queued_at": entry.queued_at,
            }
            for entry in reversed(self._pending)  # newest first (LIFO order)
        ]

        current_info = None
        if self._current:
            c = self._current
            current_info = {
                "session_id": c.session_id,
                "unit_id": c.unit_id,
                "fault_types": c.fault_types,
                "phase": c.phase,
                "stream_preview": c.stream_preview,
                "sensor_data": c.sensor_data,
                "started_at": c.started_at.isoformat(),
            }

        elapsed = int(time.time() % 300)
        if elapsed < 60:
            epoch_phase = "NORMAL"
        elif elapsed < 120:
            epoch_phase = "PRE_FAULT"
        elif elapsed < 240:
            epoch_phase = "FAULT"
        else:
            epoch_phase = "COOL_DOWN"

        epoch_num = int(time.time() // 300)

        return {
            "running": self.running,
            "is_simulated": True,
            "current": current_info,
            "pending_queue": pending_queue,
            "completed_count": self._completed_count,
            "unit_cooldowns": unit_cooldowns,
            "epoch_num": epoch_num,
            "epoch_elapsed_s": elapsed,
            "epoch_phase": epoch_phase,
        }

    async def drain(self) -> None:
        """Cancel worker and wait for it to exit (for shutdown)."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    # ── internal ─────────────────────────────────────────────────────────────

    async def _worker(self) -> None:
        while True:
            try:
                await self._wake.wait()
                self._wake.clear()
                while self._pending:
                    entry = self._pending.pop()  # LIFO: pop from right (newest)
                    await self._run_one(entry.summary)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _logger.error("worker error: %s", exc, exc_info=True)

    async def _run_one(self, summary: FaultSummary) -> None:
        session_id = f"auto-{uuid.uuid4()}"
        self._current = CurrentDiagnosisState(
            session_id=session_id,
            unit_id=summary.unit_id,
            fault_types=summary.fault_types,
            phase="sensor_reader",
            stream_preview="",
            sensor_data=[],
        )
        _token_buf: list[str] = []

        def _on_phase(phase: str) -> None:
            if self._current:
                self._current.phase = phase

        def _on_token(token: str) -> None:
            if self._current:
                _token_buf.append(token)
                full = "".join(_token_buf)
                self._current.stream_preview = full[-500:]

        def _on_sensor_data(data: list[dict]) -> None:
            if self._current:
                self._current.sensor_data = data

        from app.agents.auto_diagnosis import run_auto_diagnosis_streaming

        try:
            await run_auto_diagnosis_streaming(
                summary=summary,
                store=self._store,
                session_id=session_id,
                on_phase=_on_phase,
                on_token=_on_token,
                on_sensor_data=_on_sensor_data,
            )
            self._completed_count += 1
        except Exception as exc:
            _logger.error(
                "run_one failed | unit=%s session=%s | %s",
                summary.unit_id,
                session_id,
                exc,
                exc_info=True,
            )
        finally:
            # Clear current so get_status() returns null once the diagnosis is done
            self._current = None


# Module-level singleton
_service: AutoDiagnosisService | None = None


def get_auto_service() -> AutoDiagnosisService:
    global _service
    if _service is None:
        _service = AutoDiagnosisService()
    return _service
