from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """全局配置"""

    # === 应用 ===
    app_name: str = "企微智能运营 Agent 平台"
    debug: bool = False
    env: str = "development"

    # === vLLM / LLM ===
    vllm_base_url: str = "http://localhost:8000"
    llm_model: str = "Qwen/Qwen3-14B-AWQ"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    # 并发优化
    llm_max_concurrent: int = 8

    # === Embedding ===
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_device: str = "cuda"

    # === Reranker ===
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # === 向量数据库 ===
    chroma_persist_dir: str = "./data/vectors"
    collection_name: str = "financial_docs"

    # === PDF 解析 ===
    pdf_input_dir: str = "./data/pdfs"
    parsed_output_dir: str = "./data/parsed"

    # === 检索参数 ===
    bm25_top_k: int = 50
    vector_top_k: int = 20
    rerank_top_k: int = 10
    final_top_k: int = 3

    # === 缓存 ===
    cache_ttl_seconds: int = 300

    # === 企微 ===
    wecom_corp_id: str = ""
    wecom_agent_id: int = 1000001
    wecom_token: str = ""
    wecom_encoding_aes_key: str = ""
    wecom_callback_url: str = "/wecom/callback"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
