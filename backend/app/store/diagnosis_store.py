"""
Auto-diagnosis result store — in-memory ring buffer.

激活 config.fault_queue_max 配置项：超出容量时自动丢弃最旧的记录。
重启后清空（演示场景可接受；生产可替换为 Redis / PostgreSQL 实现同接口）。
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AutoDiagnosisRecord(BaseModel):
    """单次自动诊断结果，包含传感器触发元数据 + LangGraph 输出。"""

    session_id: str
    unit_id: str
    fault_types: list[str]
    symptom_text: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # LangGraph 输出字段（来自 AgentState）
    risk_level: str | None = None
    escalation_required: bool = False
    escalation_reason: str | None = None
    root_causes: list[dict] = Field(default_factory=list)
    check_steps: list[dict] = Field(default_factory=list)
    report_draft: str | None = None
    sources: list[str] = Field(default_factory=list)
    error: str | None = None


class DiagnosisStore:
    """线程安全（asyncio 单线程）环形缓冲区，存储最近 N 条自动诊断结果。"""

    def __init__(self, max_size: int = 5) -> None:
        self._queue: deque[AutoDiagnosisRecord] = deque(maxlen=max_size)

    def push(self, record: AutoDiagnosisRecord) -> None:
        self._queue.append(record)

    def list_all(self) -> list[AutoDiagnosisRecord]:
        """返回所有记录，最新在前。"""
        return list(reversed(self._queue))

    def __len__(self) -> int:
        return len(self._queue)


# ─── 模块级单例 ──────────────────────────────────────────────────────────────

_store: DiagnosisStore | None = None


def get_store() -> DiagnosisStore:
    """返回全局 DiagnosisStore 单例（由 config.fault_queue_max 控制容量）。"""
    global _store
    if _store is None:
        from app.config import settings
        _store = DiagnosisStore(max_size=settings.fault_queue_max)
    return _store
