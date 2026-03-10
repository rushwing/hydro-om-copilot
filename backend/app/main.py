"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import diagnosis, health
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the LangGraph compiled graph
    from app.agents.graph import get_compiled_graph
    get_compiled_graph()
    yield


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
