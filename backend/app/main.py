"""
FastAPI application entry point.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import diagnosis, health
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
    if settings.auto_random_problems_gen:
        from mcp_servers.fault_aggregator import FaultAggregator, FaultSummary

        def _on_fault(summary: FaultSummary) -> None:
            _logger.warning(
                "fault detected | unit=%s types=%s | %s",
                summary.unit_id,
                summary.fault_types,
                summary.symptom_text[:120],
            )

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
