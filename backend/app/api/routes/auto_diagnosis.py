"""
Auto-diagnosis API routes.

GET  /diagnosis/auto-results   — 查询自动诊断历史记录（保留原有端点）
GET  /diagnosis/auto/status    — 汇总状态（queue, cooldowns, epoch, current phase）
POST /diagnosis/auto/start     — 启动轮询
POST /diagnosis/auto/stop      — 停止轮询（不中断当前诊断）
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_auto_diagnosis_service, get_store
from app.services.auto_diagnosis_service import AutoDiagnosisService
from app.store.diagnosis_store import AutoDiagnosisRecord, DiagnosisStore

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


# ── Pydantic response models ──────────────────────────────────────────────────

class SensorPointSnapshot(BaseModel):
    tag: str
    name_cn: str
    value: float
    alarm_state: str
    trend: str
    thresholds: dict[str, Any]


class CurrentDiagnosisInfo(BaseModel):
    session_id: str
    unit_id: str
    fault_types: list[str]
    phase: str
    stream_preview: str
    sensor_data: list[dict[str, Any]]
    started_at: str


EpochPhase = Literal["NORMAL", "PRE_FAULT", "FAULT", "COOL_DOWN"]


class PendingFaultItem(BaseModel):
    unit_id: str
    fault_types: list[str]
    symptom_preview: str
    queued_at: str


class AutoDiagnosisStatusResponse(BaseModel):
    running: bool
    is_simulated: bool
    current: CurrentDiagnosisInfo | None
    pending_queue: list[PendingFaultItem]
    completed_count: int
    unit_cooldowns: dict[str, int]
    epoch_num: int
    epoch_elapsed_s: int
    epoch_phase: EpochPhase


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/auto-results", response_model=list[AutoDiagnosisRecord])
async def list_auto_results(
    store: DiagnosisStore = Depends(get_store),
) -> list[AutoDiagnosisRecord]:
    """
    返回最近 N 条自动诊断记录（最新在前，N = config.fault_queue_max）。

    记录由 FaultAggregator 后台轮询触发，需先设置 AUTO_RANDOM_PROBLEMS_GEN=true。
    服务重启后历史清空。
    """
    return store.list_all()


@router.get("/auto/status", response_model=AutoDiagnosisStatusResponse)
async def get_auto_status(
    service: AutoDiagnosisService = Depends(get_auto_diagnosis_service),
) -> AutoDiagnosisStatusResponse:
    """返回自动诊断服务的当前状态（队列、Epoch、冷却期、当前诊断进度）。"""
    status = service.get_status()
    return AutoDiagnosisStatusResponse(**status)


@router.post("/auto/start")
async def start_auto_diagnosis(
    service: AutoDiagnosisService = Depends(get_auto_diagnosis_service),
) -> dict:
    """启动自动诊断轮询。若已在运行则幂等返回。"""
    already_running = await service.start()
    return {"ok": True, "already_running": already_running}


@router.post("/auto/stop")
async def stop_auto_diagnosis(
    service: AutoDiagnosisService = Depends(get_auto_diagnosis_service),
) -> dict:
    """停止轮询（数据采集）。进行中的诊断可继续跑完。"""
    was_running = await service.stop()
    return {"ok": True, "polling_was_running": was_running}


@router.post("/auto/reset-cooldowns")
async def reset_cooldowns_endpoint(
    service: AutoDiagnosisService = Depends(get_auto_diagnosis_service),
) -> dict:
    """重置所有机组冷却期，使各机组立即可再次触发诊断。"""
    service.reset_cooldowns()
    return {"ok": True}
