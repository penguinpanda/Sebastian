from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Sebastian")
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    deepseek_api_key: str = Field(default="")
    deepseek_base_url: str = Field(default="https://api.deepseek.com")
    deepseek_model: str = Field(default="deepseek-chat")
    llm_timeout_ms: int = Field(default=5000)
    llm_retry_max: int = Field(default=2)
    database_url: str = Field(default="postgresql+psycopg://sebastian:sebastian@localhost:5432/sebastian")
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    db_pool_timeout: int = Field(default=30)
    db_pool_recycle_seconds: int = Field(default=1800)
    db_connect_timeout_seconds: int = Field(default=3)
    redis_url: str = Field(default="redis://localhost:6379/0")
    agent_task_status_ttl_seconds: int = Field(default=86400)
    agent_rate_limit_max_requests: int = Field(default=20)
    agent_rate_limit_window_seconds: int = Field(default=60)
    elasticsearch_url: str = Field(default="http://localhost:9200")
    elasticsearch_memory_index: str = Field(default="memory_index")
    memory_search_top_k_default: int = Field(default=5)
    memory_embedding_dims: int = Field(default=64)
    memory_embedding_provider: str = Field(default="hash")
    memory_embedding_model: str = Field(default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    memory_query_rewrite_enabled: bool = Field(default=True)
    memory_hybrid_rrf_k: int = Field(default=60)
    memory_rerank_weight_relevance: float = Field(default=0.7)
    memory_rerank_weight_recency: float = Field(default=0.2)
    memory_rerank_weight_credibility: float = Field(default=0.1)
    mcp_idempotency_ttl_seconds: int = Field(default=3600)
    mcp_auth_enabled: bool = Field(default=False)
    mcp_allowed_actions: str = Field(default="invoke")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")
    celery_scan_max_retries: int = Field(default=3)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
