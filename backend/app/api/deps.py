"""FastAPI dependency injectors."""

from functools import lru_cache

from app.agents.graph import get_compiled_graph


@lru_cache(maxsize=1)
def get_graph():
    return get_compiled_graph()
