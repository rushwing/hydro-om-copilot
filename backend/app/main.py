"""
FastAPI application entry point.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger as loguru_logger

from app.api.routes import auto_diagnosis, diagnosis, health
from app.config import settings

# ── Loguru root logger ────────────────────────────────────────────────────────
# Captures WARNING+ from all modules to logs/root.log (persistent across restarts).
# Per-session structured logs are written by app.utils.session_log.SessionLogger.

Path("logs").mkdir(exist_ok=True)
loguru_logger.remove()
loguru_logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {name}:{line} - {message}",  # noqa: E501
    colorize=True,
)
loguru_logger.add(
    "logs/root.log",
    level="WARNING",
    rotation="10 MB",
    retention="30 days",
    encoding="utf-8",
    format="{time:YYYY-MM-DDTHH:mm:ssZ} | {level} | {name}:{line} - {message}",
)

_logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm LangGraph compiled graphs
    from app.agents.graph import get_compiled_auto_graph, get_compiled_graph
    get_compiled_graph()
    get_compiled_auto_graph()

    # Start AutoDiagnosisService if opt-in via AUTO_RANDOM_PROBLEMS_GEN
    from app.services.auto_diagnosis_service import get_auto_service
    auto_service = get_auto_service()
    if settings.auto_random_problems_gen:
        await auto_service.start()
        _logger.info(
            "AutoDiagnosisService started via lifespan | poll_interval=%ds cooldown=%ds",
            settings.sensor_poll_interval_s,
            settings.diagnosis_cooldown_s,
        )

    yield

    # Shutdown: stop polling, let worker drain
    await auto_service.stop()
    await auto_service.drain()
    _logger.info("AutoDiagnosisService shut down")


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
