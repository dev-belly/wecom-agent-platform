"""Environment-backed application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global service configuration."""

    app_name: str = "企微智能运营 Agent 平台"
    debug: bool = False
    env: str = "development"
    api_key: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    vllm_base_url: str = "http://localhost:8000"
    llm_model: str = "Qwen/Qwen3-14B-AWQ"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_max_concurrent: int = 8

    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_device: str = "cuda"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    chroma_persist_dir: str = "./data/vectors"
    collection_name: str = "financial_docs"

    pdf_input_dir: str = "./data/pdfs"
    parsed_output_dir: str = "./data/parsed"
    eval_data_dir: str = "./data/eval"

    bm25_top_k: int = 50
    vector_top_k: int = 20
    rerank_top_k: int = 10
    final_top_k: int = 3
    cache_ttl_seconds: int = 300

    wecom_corp_id: str = ""
    wecom_agent_id: int = 1000001
    wecom_token: str = ""
    wecom_encoding_aes_key: str = ""
    wecom_callback_url: str = "/wecom/callback"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
