from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "MediAssist"
    app_env: str = "development"
    debug: bool = True

    # LLM (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_device: str = "cpu"

    # Vector store (Qdrant)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "mediassist_policies"

    # Database
    database_url: str = "sqlite:///./data/mediassist.db"

    # Retrieval
    top_k: int = 5
    rerank_top_k: int = 10


settings = Settings()