"""vLLM Qwen3-14B AWQ 客户端 — 缓存 / 异步 / 并发优化"""

from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from typing import Optional, Any

import httpx
from cachetools import TTLCache
from loguru import logger

from config.settings import get_settings


# ── 语义缓存（相同/相似查询复用结果）─

class SemanticCache:
    """
    基于哈希的语义缓存

    - 对 prompt 做归一化后取 hash 作为 key
    - TTL 自动过期
    - 命中时直接返回缓存结果，跳过 LLM 调用
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _normalize(prompt: str) -> str:
        """归一化 prompt：去空白、统一大小写、排序 JSON key"""
        # 尝试解析 JSON prompt 并标准化
        try:
            obj = json.loads(prompt)
            prompt = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (json.JSONDecodeError, TypeError):
            pass
        return " ".join(prompt.lower().split())

    def _key(self, model: str, messages: list[dict], **extra) -> str:
        """生成缓存 key"""
        raw = json.dumps({
            "model": model,
            "messages": [(m.get("role", ""), m.get("content", "")) for m in messages],
            **extra,
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, model: str, messages: list[dict], **extra) -> Optional[str]:
        """查缓存"""
        k = self._key(model, messages, **extra)
        result = self.cache.get(k)
        if result is not None:
            self.hits += 1
            logger.debug(f"缓存命中: {k[:12]}...")
        else:
            self.misses += 1
        return result

    def set(self, model: str, messages: list[dict], response_text: str, **extra) -> None:
        """写入缓存"""
        k = self._key(model, messages, **extra)
        self.cache[k] = response_text

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total > 0 else 0,
            "size": len(self.cache),
        }


# ── 异步并发客户端 ────────────────────────────────────

class AsyncLLMClient:
    """
    异步 vLLM 客户端

    特性：
      - 连接池复用（httpx AsyncClient）
      - 请求级并发控制（Semaphore）
      - 语义缓存
      - 自动重试（tenacity）
      - 请求/响应日志追踪
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.vllm_base_url.rstrip("/")
        self.model = self.settings.llm_model

        # HTTP 连接池
        self._client: Optional[httpx.AsyncClient] = None

        # 并发信号量
        import asyncio
        self._semaphore = asyncio.Semaphore(self.settings.llm_max_concurrent)

        # 语义缓存
        self.cache = SemanticCache(
            max_size=2000,
            ttl_seconds=self.settings.cache_ttl_seconds,
        )

        # 统计
        self._request_count = 0
        self._cache_count = 0
        self._total_latency = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        """懒初始化 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """关闭连接池"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── 核心 API ──────────────────────────────────────

    async def chat_completions_create(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """
        调用 vLLM chat completions API（带缓存 + 并发控制）

        Returns:
            与 OpenAI 兼容的响应字典
        """
        model = model or self.model
        t0 = time.perf_counter()

        # 1. 查缓存
        cached = self.cache.get(model, messages, temperature=temperature, max_tokens=max_tokens)
        if cached is not None:
            self._cache_count += 1
            return {"choices": [{"message": {"content": cached}}], "cached": True}

        # 2. 并发控制
        async with self._semaphore:
            client = await self._get_client()
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }
            if response_format:
                payload["response_format"] = response_format

            retry_count = 0
            last_exc = None

            for attempt in range(3):  # 最多重试 3 次
                try:
                    resp = await client.post("/v1/chat/completions", json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                    # 写缓存
                    content = data["choices"][0]["message"]["content"]
                    self.cache.set(model, messages, content, temperature=temperature, max_tokens=max_tokens)

                    latency = time.perf_counter() - t0
                    self._request_count += 1
                    self._total_latency += latency

                    if latency > 1.0:
                        logger.warning(f"LLM 调用较慢: {latency:.2f}s, model={model}")

                    return data

                except httpx.HTTPStatusError as e:
                    last_exc = e
                    retry_count += 1
                    if e.response.status_code >= 500:
                        await asyncio.sleep(1 * attempt)  # 指数退避
                        continue
                    raise
                except Exception as e:
                    last_exc = e
                    retry_count += 1
                    await asyncio.sleep(0.5 * attempt)

            raise RuntimeError(f"vLLM 调用失败(重试{retry_count}次): {last_exc}")

    async def embeddings_create(self, input_text: str | list[str], model: str = "") -> dict:
        """调用 embedding API（备用方案）"""
        client = await self._get_client()
        resp = await client.post("/v1/embeddings", json={
            "model": model or self.settings.embedding_model,
            "input": input_text,
        })
        resp.raise_for_status()
        return resp.json()

    # ── 统计 & 监控 ──────────────────────────────────

    def stats(self) -> dict:
        """性能统计"""
        avg_latency = self._total_latency / max(self._request_count, 1)
        return {
            "total_requests": self._request_count,
            "cache_hits": self._cache_count,
            "cache_hit_rate": round(self._cache_count / max(self._request_count + self._cache_count, 1), 4),
            "avg_latency_ms": round(avg_latency * 1000, 1),
            "cache_stats": self.cache.stats(),
        }

    # ── 兼容层：模拟 openai.OpenAI 接口 ───────────────

    class ChatCompletions:
        """模拟 openai.Chat.completions 接口"""

        def __init__(self, parent: "AsyncLLMClient"):
            self._parent = parent

        async def create(self, **kwargs) -> Any:
            return await self._parent.chat_completions_create(**kwargs)

    @property
    def chat(self):
        return self.ChatCompletions(self)


# ── 同步包装（用于非 async 场景）─

class SyncLLMClient:
    """同步版 LLM 客户端（内部用线程跑 async）"""
    import asyncio

    def __init__(self):
        self._async_client = AsyncLLMClient()
        self._loop = None

    def _get_loop(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop

    def chat_completions_create(self, **kwargs) -> dict:
        return self._get_loop().run_until_complete(
            self._async_client.chat_completions_create(**kwargs)
        )

    @property
    def chat):
        return self._SyncChat(self)

    class _SyncChat:
        def __init__(self, parent: "SyncLLMClient"):
            self._parent = parent

        def create(self, **kwargs):
            return self._parent.chat_completions_create(**kwargs)


# ── 单例管理 ──────────────────────────────────────────

_llm_client_instance: Optional[AsyncLLMClient] = None


def get_llm_client(async_mode: bool = True):
    """获取 LLM 客户端单例"""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = AsyncLLMClient() if async_mode else SyncLLMClient()
    return _llm_client_instance


# ── 启动时预热 ────────────────────────────────────────

async def warmup():
    """启动时预热：发送一个简单请求建立连接和模型加载"""
    client = get_llm_client()
    try:
        start = time.time()
        await client.chat_completions_create(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=8,
        )
        elapsed = time.time() - start
        logger.info(f"✅ vLLM 预热完成，首请求耗时 {elapsed:.2f}s")
    except Exception as e:
        logger.warning(f"⚠️ vLLM 预热失败（服务可能尚未就绪）: {e}")


import asyncio
