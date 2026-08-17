"""FastAPI 服务层 — 企微回调 / RESTful API / 健康检查"""

from __future__ import annotations

import json
import time
import traceback
from contextlib import asynccontextmanager
from typing import Optional, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from config.settings import get_settings
from retrieval.hybrid_retriever import HybridRetriever
from agents.financial_agent import FinancialAgentGraph
from models.llm_client import get_llm_client, warmup
from parsers.pdf_parser import FinancialPDFParser


# ── 请求/响应模型 ─────────────────────────────────────

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID（用于多轮上下文）")
    history: Optional[list[dict]] = Field(None, description="历史消息")


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
    eval_file: str = Field(..., description="评估数据集文件路径")


# ── 全局状态 ──────────────────────────────────────────

settings = get_settings()
retriever: Optional[HybridRetriever] = None
agent_graph: Optional[FinancialAgentGraph] = None
_app_ready = False


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
    from pathlib import Path
    parsed_files = list(Path(parsed_dir).glob("*.json")) if Path(parsed_dir).exists() else []

    if parsed_files:
        from parsers.pdf_parser import ParsedDocument
        docs = []
        for pf in parsed_files:
            data = json.loads(pf.read_text(encoding="utf-8"))
            doc = ParsedDocument(
                source_file=data["source_file"],
                total_pages=data["total_pages"],
                metadata=data.get("metadata", {}),
            )
            docs.append(doc)
        retriever.build_index_from_parsed(docs)
        logger.info(f"📊 从 {len(docs)} 份已解析文档恢复索引")
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    主聊天接口

    用户消息 → Agent 推理 → 结构化回复
    """
    if not _app_ready:
        raise HTTPException(status_code=503, detail="服务尚未就绪")

    t0 = time.perf_counter()
    trace_id = f"{int(time.time()*1000)}"

    try:
        result = await agent_graph.run(
            user_message=req.message,
            chat_history=req.history,
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
        raise HTTPException(status_code=500, detail=str(e))


# ── 企微回调 ──────────────────────────────────────────

@app.post(settings.wecom_callback_url)
async def wecom_callback(request: Request, background_tasks: BackgroundTasks):
    """
    企业微信消息回调

    处理企微推送的用户消息，异步处理后回传结果
    """
    body = await request.body()
    data = json.loads(body)

    logger.debug(f"企微回调: {data}")

    # TODO: 验签（MsgSignature + Timestamp + Nonce + Encrypt）

    msg_type = data.get("MsgType", "")

    if msg_type == "text":
        user_msg = data.get("Content", "")
        from_user = data.get("FromUserName", "")

        # 异步处理，避免超时
        background_tasks.add_task(_handle_wecom_message, user_msg, from_user)

        return {"code": 0, "msg": "success"}

    elif msg_type == "event":
        event = data.get("Event", "")
        if event == "subscribe":
            logger.info(f"新用户关注: {data.get('FromUserName')}")
        return {"code": 0, "msg": "success"}

    return {"code": 0, "msg": "ok"}


async def _handle_wecom_message(user_msg: str, from_user: str):
    """处理企微消息并回传"""
    try:
        result = await agent_graph.run(user_message=user_msg)
        reply = result.get("final_response", "抱歉，暂时无法处理。")

        # TODO: 调用企微 API 发送被动回复
        logger.info(f"企微回复 [{from_user}]: {reply[:100]}")

    except Exception as e:
        logger.error(f"企微消息处理失败: {e}")


# ── 索引管理 ──────────────────────────────────────────

@app.post("/api/index/build")
async def build_index(req: BuildIndexRequest):
    """触发 PDF 解析 + 索引构建"""
    parser = FinancialPDFParser(settings.pdf_input_dir, settings.parsed_output_dir)
    docs = parser.parse_all()

    if req.force_rebuild or not retriever._initialized:
        retriever.build_index_from_parsed(docs)

    return {
        "status": "ok",
        "documents_parsed": len(docs),
        "tables_total": sum(len(d.tables) for d in docs),
        "index_initialized": retriever._initialized,
    }


@app.get("/api/index/status")
async def index_status():
    """查看索引状态"""
    collection = retriever.collection if retriever else None
    return {
        "initialized": retriever._initialized if retriever else False,
        "document_count": collection.count() if collection else 0,
        "bm25_docs": len(retriever.bm25_docs) if retriever else 0,
    }


# ── 评估接口 ──────────────────────────────────────────

@app.post("/api/eval")
async def run_evaluation(req: EvalRequest):
    """运行检索质量评估"""
    from retrieval.hybrid_retriever import RetrievalEvaluator

    eval_path = Path(req.eval_file)
    if not eval_path.exists():
        raise HTTPException(status_code=404, detail=f"评估文件不存在: {req.eval_file}")

    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    evaluator = RetrievalEvaluator(retriever)
    metrics = evaluator.evaluate(eval_data)

    return {"eval_result": metrics}


# ── 性能监控 ──────────────────────────────────────────

@app.get("/api/stats")
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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
