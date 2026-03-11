"""
GET /diagnosis/auto-results — 查询自动诊断历史记录。
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_store
from app.store.diagnosis_store import AutoDiagnosisRecord, DiagnosisStore

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


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
