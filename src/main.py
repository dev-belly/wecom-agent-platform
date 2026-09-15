"""FastAPI 服务层 — 企微回调 / RESTful API / 健康检查"""

from __future__ import annotations

import json
import secrets
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional
from xml.etree import ElementTree

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from src.agents.financial_agent import FinancialAgentGraph
from src.config.settings import get_settings
from src.models.llm_client import get_llm_client, warmup
from src.parsers.pdf_parser import FinancialPDFParser
from src.retrieval.hybrid_retriever import HybridRetriever
from src.services.wecom_crypto import WeComCryptoError, decrypt_message, verify_signature

# ── 请求/响应模型 ─────────────────────────────────────

class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: Optional[str] = Field(None, min_length=1, max_length=64, description="会话追踪 ID")
    history: Optional[list[ChatHistoryItem]] = Field(None, max_length=50, description="历史消息")

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        return value


class ChatResponse(BaseModel):
    """聊天响应"""
    reply: str
    trace_id: str = ""
    intent: str = ""
    latency_ms: float = 0.0
    tool_used: str = ""
    error: Optional[str] = None


class BuildIndexRequest(BaseModel):
    """构建索引请求"""
    force_rebuild: bool = Field(False, description="是否强制重建")


class EvalRequest(BaseModel):
    """评估请求"""
    eval_file: str = Field(..., min_length=1, max_length=300, description="data/eval 下的 JSON 文件")


# ── 全局状态 ──────────────────────────────────────────

settings = get_settings()
retriever: Optional[HybridRetriever] = None
agent_graph: Optional[FinancialAgentGraph] = None
_app_ready = False


async def require_api_key(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> None:
    """Protect business data while retaining a zero-config local demo mode."""
    configured = settings.api_key.strip()
    if len(configured) < 32:
        if settings.is_production:
            raise HTTPException(status_code=503, detail="生产环境 API_KEY 未配置或长度不足 32 位")
        if configured:
            logger.warning("开发环境 API_KEY 长度不足 32 位，仅适合本地调试")
        else:
            return
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    candidate = x_api_key or bearer
    if not candidate or not secrets.compare_digest(candidate, configured):
        raise HTTPException(
            status_code=401,
            detail="API 密钥无效",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── 应用生命周期 ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期"""
    global retriever, agent_graph, _app_ready

    logger.info("🚀 企微智能运营 Agent 平台 启动中...")

    # 1. 初始化检索器
    retriever = HybridRetriever()

    # 2. 检查是否有已解析的数据，有则自动建索引
    parsed_dir = settings.parsed_output_dir
    parsed_files = list(Path(parsed_dir).glob("*.json")) if Path(parsed_dir).exists() else []

    if parsed_files:
        from src.parsers.pdf_parser import ParsedDocument
        docs = []
        for pf in parsed_files:
            try:
                data = json.loads(pf.read_text(encoding="utf-8"))
                docs.append(ParsedDocument.from_dict(data))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                logger.error(f"跳过损坏的解析文件 {pf.name}: {exc}")
        if docs:
            try:
                retriever.build_index_from_parsed(docs)
                logger.info(f"📊 从 {len(docs)} 份已解析文档恢复索引")
            except (RuntimeError, ValueError) as exc:
                logger.warning(f"检索索引未恢复: {exc}")
    else:
        logger.info("⏳ 无已解析数据，等待手动触发 PDF 解析和索引构建")

    # 3. 初始化 LLM 客户端 & 预热
    try:
        llm_client = get_llm_client()
        await warmup()
    except Exception as e:
        logger.warning(f"LLM 客户端初始化失败: {e}，部分功能将不可用")

    # 4. 构建 Agent 图
    llm_client = get_llm_client()
    agent_graph = FinancialAgentGraph(retriever, llm_client)

    _app_ready = True
    logger.info("✅ 服务就绪")

    yield

    # 关闭资源
    llm_client = get_llm_client()
    if hasattr(llm_client, 'close'):
        await llm_client.close()
    logger.info("👋 服务已关闭")


# ── 创建 App ──────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


# ── 健康检查 ──────────────────────────────────────────

@app.get("/health")
async def health_check():
    """健康检查端点"""
    llm_stats = {}
    try:
        llm_client = get_llm_client()
        llm_stats = llm_client.stats()
    except Exception:
        pass

    return {
        "status": "ready" if _app_ready else "booting",
        "retriever": retriever is not None and retriever._initialized,
        "llm": llm_stats,
        "timestamp": time.time(),
    }


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "/api/chat",
            "health": "/health",
            "wecom_callback": "/wecom/callback",
            "build_index": "/api/index/build",
            "eval": "/api/eval",
        },
    }


# ── 核心：聊天接口 ────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    """
    主聊天接口

    用户消息 → Agent 推理 → 结构化回复
    """
    if not _app_ready or agent_graph is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")

    t0 = time.perf_counter()
    trace_id = f"{int(time.time()*1000)}"

    try:
        result = await agent_graph.run(
            user_message=req.message,
            chat_history=[item.model_dump() for item in req.history] if req.history else None,
            trace_id=trace_id,
        )

        latency = (time.perf_counter() - t0) * 1000

        return ChatResponse(
            reply=result.get("final_response") or result.get("error") or "抱歉，暂时无法处理您的请求。",
            trace_id=result.get("trace_id", trace_id),
            intent=result.get("intent", ""),
            latency_ms=round(latency, 1),
            tool_used=result.get("intent", ""),
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"聊天处理异常: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="聊天服务暂时不可用") from e


# ── 企微回调 ──────────────────────────────────────────

def _parse_wecom_xml(source: str) -> dict[str, str]:
    if "<!DOCTYPE" in source.upper() or "<!ENTITY" in source.upper():
        raise ValueError("不允许 XML 实体声明")
    root = ElementTree.fromstring(source)
    return {child.tag: child.text or "" for child in root}


def _ensure_wecom_configured() -> None:
    if not (settings.wecom_token and settings.wecom_encoding_aes_key and settings.wecom_corp_id):
        raise HTTPException(status_code=503, detail="企业微信回调尚未安全配置")


@app.get(settings.wecom_callback_url, response_class=PlainTextResponse)
async def verify_wecom_callback(
    msg_signature: str = Query(..., min_length=40, max_length=40),
    timestamp: str = Query(..., min_length=1, max_length=20),
    nonce: str = Query(..., min_length=1, max_length=128),
    echostr: str = Query(..., min_length=1, max_length=8192),
):
    """Handle WeCom URL verification without ever accepting plaintext callbacks."""
    _ensure_wecom_configured()
    if not verify_signature(settings.wecom_token, msg_signature, timestamp, nonce, echostr):
        raise HTTPException(status_code=403, detail="企业微信回调签名无效")
    try:
        return decrypt_message(settings.wecom_encoding_aes_key, echostr, settings.wecom_corp_id)
    except WeComCryptoError as exc:
        raise HTTPException(status_code=403, detail="企业微信回调解密失败") from exc


@app.post(settings.wecom_callback_url, response_class=PlainTextResponse)
async def wecom_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    msg_signature: str = Query(..., min_length=40, max_length=40),
    timestamp: str = Query(..., min_length=1, max_length=20),
    nonce: str = Query(..., min_length=1, max_length=128),
):
    """
    企业微信消息回调

    处理企微推送的用户消息，异步处理后回传结果
    """
    _ensure_wecom_configured()
    body = await request.body()
    if not body or len(body) > 128 * 1024:
        raise HTTPException(status_code=400, detail="企业微信回调内容无效")
    try:
        envelope = _parse_wecom_xml(body.decode("utf-8"))
        encrypted = envelope.get("Encrypt", "")
        if not verify_signature(
            settings.wecom_token, msg_signature, timestamp, nonce, encrypted,
        ):
            raise HTTPException(status_code=403, detail="企业微信回调签名无效")
        plaintext = decrypt_message(
            settings.wecom_encoding_aes_key, encrypted, settings.wecom_corp_id,
        )
        data = _parse_wecom_xml(plaintext)
    except HTTPException:
        raise
    except (UnicodeDecodeError, ElementTree.ParseError, ValueError, WeComCryptoError) as exc:
        raise HTTPException(status_code=400, detail="企业微信回调格式无效") from exc

    logger.debug(f"企微回调类型: {data.get('MsgType', '')}")

    msg_type = data.get("MsgType", "")

    if msg_type == "text":
        user_msg = data.get("Content", "")
        from_user = data.get("FromUserName", "")

        # 异步处理，避免超时
        background_tasks.add_task(_handle_wecom_message, user_msg, from_user)

        return "success"

    elif msg_type == "event":
        event = data.get("Event", "")
        if event == "subscribe":
            logger.info(f"新用户关注: {data.get('FromUserName')}")
        return "success"

    return "success"


async def _handle_wecom_message(user_msg: str, from_user: str):
    """处理企微消息并回传"""
    try:
        if agent_graph is None:
            logger.error("企微消息未处理：Agent 服务尚未就绪")
            return
        result = await agent_graph.run(user_message=user_msg)
        reply = result.get("final_response", "抱歉，暂时无法处理。")

        # TODO: 调用企微 API 发送被动回复
        logger.info(f"企微回复 [{from_user}]: {reply[:100]}")

    except Exception as e:
        logger.error(f"企微消息处理失败: {e}")


# ── 索引管理 ──────────────────────────────────────────

@app.post("/api/index/build", dependencies=[Depends(require_api_key)])
async def build_index(req: BuildIndexRequest):
    """触发 PDF 解析 + 索引构建"""
    parser = FinancialPDFParser(settings.pdf_input_dir, settings.parsed_output_dir)
    docs = parser.parse_all()

    if not docs:
        raise HTTPException(status_code=422, detail="PDF 目录中没有可解析文档")
    if retriever is None:
        raise HTTPException(status_code=503, detail="检索服务尚未就绪")
    if req.force_rebuild or not retriever._initialized:
        retriever.build_index_from_parsed(docs)

    return {
        "status": "ok",
        "documents_parsed": len(docs),
        "tables_total": sum(len(d.tables) for d in docs),
        "index_initialized": retriever._initialized,
    }


@app.get("/api/index/status", dependencies=[Depends(require_api_key)])
async def index_status():
    """查看索引状态"""
    collection = retriever.collection if retriever else None
    return {
        "initialized": retriever._initialized if retriever else False,
        "document_count": collection.count() if collection else 0,
        "bm25_docs": len(retriever.bm25_docs) if retriever else 0,
    }


# ── 评估接口 ──────────────────────────────────────────

@app.post("/api/eval", dependencies=[Depends(require_api_key)])
async def run_evaluation(req: EvalRequest):
    """运行检索质量评估"""
    from src.retrieval.hybrid_retriever import RetrievalEvaluator

    eval_root = Path(settings.eval_data_dir).resolve()
    candidate = Path(req.eval_file)
    eval_path = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    try:
        eval_path.relative_to(eval_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="评估文件必须位于 data/eval 目录") from exc
    if eval_path.suffix.lower() != ".json":
        raise HTTPException(status_code=400, detail="评估文件必须是 JSON")
    if not eval_path.exists():
        raise HTTPException(status_code=404, detail="评估文件不存在")
    if eval_path.stat().st_size > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="评估文件不能超过 5 MB")

    try:
        eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="评估文件无法解析") from exc
    if not isinstance(eval_data, list):
        raise HTTPException(status_code=400, detail="评估数据必须是数组")
    if retriever is None or not retriever._initialized:
        raise HTTPException(status_code=409, detail="请先构建检索索引")
    evaluator = RetrievalEvaluator(retriever)
    try:
        metrics = evaluator.evaluate(eval_data)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="评估数据格式无效") from exc

    return {"eval_result": metrics}


# ── 性能监控 ──────────────────────────────────────────

@app.get("/api/stats", dependencies=[Depends(require_api_key)])
async def performance_stats():
    """获取性能统计数据"""
    llm_stats = {}
    try:
        llm_client = get_llm_client()
        llm_stats = llm_client.stats()
    except Exception:
        pass

    return {
        "llm": llm_stats,
        "retriever": {
            "initialized": retriever._initialized if retriever else False,
            "bm25_docs": len(retriever.bm25_docs) if retriever else 0,
            "vector_count": retriever.collection.count() if retriever and retriever.collection else 0,
        } if retriever else {},
    }


# ── 启动入口 ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=9000,
        reload=settings.debug,
    )
