"""
Session-scoped structured log writer.

Each diagnosis session gets its own directory under logs/sessions/pending/:

  logs/sessions/pending/<unit_slug>/<YYYY-MM-DD>/<YYYYMMDD_HHMMSS>_<fault>_<sid8>/
      pipeline.log   — JSON-lines: node start/end/error events + metadata
      api_calls.log  — JSON-lines: Anthropic API call timing and token usage
      meta.json      — Quick-scan metadata (updated on finalize)

When a session is archived (user submits), the caller should rename
pending/<unit>/<date>/<session>/ → archived/<unit>/<date>/<session>/.
(TODO: implement rename on archive — see todo.md)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

_std_logger = logging.getLogger("app.utils.session_log")

# ── Constants ─────────────────────────────────────────────────────────────────

LOGS_ROOT = Path("logs")

FAULT_TYPE_SHORT: dict[str, str] = {
    "vibration_swing": "vibration",
    "governor_oil_pressure": "gov_oil_press",
    "bearing_temp_cooling": "bearing_temp",
    "manual": "manual",
    "auto": "auto",
}

# ── SessionLogger ─────────────────────────────────────────────────────────────


class SessionLogger:
    """
    Writes structured JSON-lines logs for a single diagnosis session.

    Thread/async-safe for single-writer usage (one session per log file).
    """

    def __init__(self, session_id: str, unit_id: str, fault_type: str) -> None:
        self.session_id = session_id
        self._started_at = datetime.now(UTC)

        # Sanitize unit_id for filesystem (e.g. "#1机" → "1_unit")
        unit_slug = (
            unit_id.replace("#", "").replace("机", "_unit")
            .strip("_").replace(" ", "_") or "unknown"
        )
        date_str = self._started_at.strftime("%Y-%m-%d")
        time_str = self._started_at.strftime("%Y%m%d_%H%M%S")
        ft = FAULT_TYPE_SHORT.get(fault_type, fault_type[:12])
        sid8 = session_id.replace("auto-", "").replace("-", "")[:8]

        self._dir = (
            LOGS_ROOT / "sessions" / "pending" / unit_slug / date_str
            / f"{time_str}_{ft}_{sid8}"
        )
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _std_logger.warning("session_log: cannot create dir %s: %s", self._dir, exc)

        self._pipeline_path = self._dir / "pipeline.log"
        self._api_path = self._dir / "api_calls.log"

        self._meta: dict = {
            "session_id": session_id,
            "unit_id": unit_id,
            "fault_type": fault_type,
            "risk_level": None,
            "started_at": self._started_at.isoformat(),
            "finalized_at": None,
            "sop_steps_total": 0,
            "escalation_required": False,
            "top_cause": None,
            "error": None,
        }
        self._flush_meta()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _write(self, path: Path, entry: dict) -> None:
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            _std_logger.debug("session_log write failed: %s", exc)

    def _flush_meta(self) -> None:
        try:
            (self._dir / "meta.json").write_text(
                json.dumps(self._meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            _std_logger.debug("session_log meta write failed: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def pipeline(self, node: str, event: str, **extra: object) -> None:
        """Log a pipeline event (node start / end / error / custom)."""
        entry: dict = {
            "ts": datetime.now(UTC).isoformat(),
            "node": node,
            "event": event,
        }
        if extra:
            entry.update(extra)
        self._write(self._pipeline_path, entry)

    def api_call(
        self,
        *,
        node: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        ok: bool,
        error: str = "",
    ) -> None:
        """Log a single Anthropic API call with timing and token counts."""
        entry: dict = {
            "ts": datetime.now(UTC).isoformat(),
            "node": node,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(latency_ms, 1),
            "ok": ok,
        }
        if error:
            entry["error"] = error
        self._write(self._api_path, entry)

    def finalize(
        self,
        *,
        risk_level: str | None = None,
        top_cause: str | None = None,
        escalation_required: bool = False,
        sop_steps_total: int = 0,
        fault_type: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update meta.json with final session outcome."""
        self._meta.update(
            {
                "risk_level": risk_level,
                "top_cause": top_cause,
                "escalation_required": escalation_required,
                "sop_steps_total": sop_steps_total,
                "finalized_at": datetime.now(UTC).isoformat(),
                "error": error,
            }
        )
        if fault_type:
            self._meta["fault_type"] = fault_type
        self._flush_meta()
        self.pipeline("__session__", "finalized", error=error or "")

    @property
    def dir(self) -> Path:
        return self._dir


# ── Registry ──────────────────────────────────────────────────────────────────

_registry: dict[str, SessionLogger] = {}


def create_session_logger(session_id: str, unit_id: str, fault_type: str) -> SessionLogger:
    sl = SessionLogger(session_id, unit_id, fault_type)
    _registry[session_id] = sl
    return sl


def get_session_logger(session_id: str) -> SessionLogger | None:
    return _registry.get(session_id)


def remove_session_logger(session_id: str) -> None:
    _registry.pop(session_id, None)
