"""
FastAPI application entry point.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auto_diagnosis, diagnosis, health
from app.config import settings

_logger = logging.getLogger("app.main")

# 默认监控机组列表（演示场景固定 4 台）
_MONITORED_UNITS = ["#1机", "#2机", "#3机", "#4机"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the LangGraph compiled graph
    from app.agents.graph import get_compiled_graph
    get_compiled_graph()

    # Start FaultAggregator background polling task (opt-in via AUTO_RANDOM_PROBLEMS_GEN)
    polling_task: asyncio.Task | None = None
    _diagnosis_tasks: set[asyncio.Task] = set()
    if settings.auto_random_problems_gen:
        from app.agents.auto_diagnosis import run_auto_diagnosis
        from app.store.diagnosis_store import get_store
        from mcp_servers.fault_aggregator import FaultAggregator, FaultSummary

        _store = get_store()

        async def _run_auto_diagnosis(summary: FaultSummary) -> None:
            await run_auto_diagnosis(summary, _store)

        def _on_fault(summary: FaultSummary) -> None:
            _logger.warning(
                "fault detected | unit=%s types=%s | %s",
                summary.unit_id,
                summary.fault_types,
                summary.symptom_text[:120],
            )
            task = asyncio.create_task(_run_auto_diagnosis(summary))
            _diagnosis_tasks.add(task)
            task.add_done_callback(_diagnosis_tasks.discard)

        agg = FaultAggregator(cooldown_s=settings.diagnosis_cooldown_s)
        polling_task = asyncio.create_task(
            agg.run_polling_loop(
                _MONITORED_UNITS,
                interval_s=settings.sensor_poll_interval_s,
                on_fault=_on_fault,
            )
        )
        _logger.info(
            "FaultAggregator started | units=%s poll_interval=%ds cooldown=%ds",
            _MONITORED_UNITS,
            settings.sensor_poll_interval_s,
            settings.diagnosis_cooldown_s,
        )

    yield

    if polling_task is not None:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        _logger.info("FaultAggregator stopped")

    # Drain in-flight auto-diagnosis tasks before exit
    if _diagnosis_tasks:
        await asyncio.gather(*_diagnosis_tasks, return_exceptions=True)
        _logger.info("in-flight diagnosis tasks drained | count=%d", len(_diagnosis_tasks))


app = FastAPI(
    title="Hydro O&M Copilot API",
    description="水电机组异常诊断辅助系统 — 仅作辅助决策，不替代现场工程师判断",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(diagnosis.router)
app.include_router(auto_diagnosis.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
