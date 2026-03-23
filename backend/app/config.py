import json
from typing import Any

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _CommaSepMixin:
    """Decode comma-separated strings for list fields.

    Applied to both the OS-env source and the dotenv source so that
    ``CORS_ORIGINS=http://localhost:5173,http://localhost:3000`` works in
    either location.
    """

    def decode_complex_value(self, field_name: str, field: Any, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.startswith(("[", "{")):
                return json.loads(stripped)
            # comma-separated fallback (e.g. CORS_ORIGINS=a,b,c)
            return [x.strip() for x in stripped.split(",") if x.strip()]
        return super().decode_complex_value(field_name, field, value)  # type: ignore[misc]


class _EnvSource(_CommaSepMixin, EnvSettingsSource):
    """OS environment variables with comma-sep list support."""


class _DotEnvSource(_CommaSepMixin, DotEnvSettingsSource):
    """.env file with comma-sep list support."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM — primary (Anthropic)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_auth_token: str = Field(default="", alias="ANTHROPIC_AUTH_TOKEN")
    anthropic_api_base: str = Field(default="https://api.anthropic.com", alias="ANTHROPIC_API_BASE")
    llm_model: str = "claude-sonnet-4-6"
    llm_temperature: float = 0.1

    # LLM — fallback (OpenAI)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_api_base: str = Field(default="https://api.openai.com/v1", alias="OPENAI_API_BASE")
    fallback_llm_model: str = Field(default="gpt-4.5", alias="FALLBACK_LLM_MODEL")

    # Vector store
    vector_store_type: str = "chroma"  # chroma | qdrant
    chroma_persist_dir: str = "./knowledge_base/vector_store"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "hydro_kb"

    # Embedding / Reranker
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 5

    # Knowledge base
    kb_docs_dir: str = "./knowledge_base/docs_internal"

    # Chunking — prose documents
    chunk_size: int = 600
    chunk_overlap: int = 80
    # Chunking — L3 stub documents (sparse template content)
    chunk_size_l3: int = 300
    chunk_overlap_l3: int = 40
    # Chunking — Markdown tables (max data rows per chunk, header always prepended)
    table_rows_per_chunk: int = 20

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # LangSmith (optional)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "hydro-om-copilot"

    # Sensor / pseudo-random fault generation
    auto_random_problems_gen: bool = Field(
        default=False, validation_alias="AUTO_RANDOM_PROBLEMS_GEN"
    )
    sensor_poll_interval_s: int = Field(
        default=15, validation_alias="SENSOR_POLL_INTERVAL"
    )
    fault_collection_window_s: int = Field(
        default=60, validation_alias="FAULT_COLLECTION_WINDOW"
    )
    diagnosis_cooldown_s: int = Field(
        default=300, validation_alias="DIAGNOSIS_COOLDOWN"
    )
    fault_queue_max: int = Field(default=5, validation_alias="FAULT_QUEUE_MAX")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _EnvSource(settings_cls),
            _DotEnvSource(settings_cls),
            file_secret_settings,
        )


settings = Settings()
