from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-sonnet-4-6"
    llm_temperature: float = 0.1

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

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # LangSmith (optional)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "hydro-om-copilot"


settings = Settings()
