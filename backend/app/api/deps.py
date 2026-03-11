"""FastAPI dependency injectors."""

from functools import lru_cache

from app.agents.graph import get_compiled_graph
from app.store.diagnosis_store import DiagnosisStore
from app.store.diagnosis_store import get_store as _get_store


@lru_cache(maxsize=1)
def get_graph():
    return get_compiled_graph()


def get_store() -> DiagnosisStore:
    return _get_store()
