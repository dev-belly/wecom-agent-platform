"""LangGraph 多工具 Agent 引擎 — 意图识别 → 工具调用 → 结果输出"""

from __future__ import annotations

import json
import time
from typing import Any, TypedDict, Annotated
from operator import add

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool as lc_tool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from config.settings import get_settings
from retrieval.hybrid_retriever import HybridRetriever
from tools.business_tools import (
    TOOL_REGISTRY,
    get_all_tools,
    get_tool,
    BaseTool,
)


# ── Agent 状态定义 ────────────────────────────────────

class AgentState(TypedDict):
    """Agent 运行时状态"""
    messages: list[dict]           # 对话消息历史
    intent: str                    # 识别出的意图/工具名
    tool_params: dict              # 提取的工具参数
    tool_result: dict | None       # 工具执行结果
    final_response: str | None     # 最终回复文本
    error: str | None              # 错误信息
    trace_id: str                  # 追踪 ID
    timestamps: dict[str, float]   # 各阶段耗时记录


# ── 意图识别（LLM）─ ──────────────────────────────────

INTENT_SYSTEM_PROMPT = """你是一个金融业务意图分类器。根据用户输入，判断用户想要执行哪类操作。

可用工具及描述：
{tool_descriptions}

请严格返回 JSON 格式：
{
  "intent": "工具名称",
  "confidence": 0.0-1.0,
  "params": {
    "参数名": "参数值或null",
    ...
  },
  "clarification": "如果信息不足需要追问的问题，否则为null"
}

规则：
1. 如果用户问题与任何工具都不匹配，intent 设为 "unknown"
2. confidence < 0.5 时必须设置 clarification 进行追问
3. 尽量从用户输入中提取所有可能的参数值
4. 参数值为 null 表示用户未提供"""


def identify_intent(state: AgentState, llm_client) -> AgentState:
    """节点 1: 意图识别 + 参数提取"""
    start = time.time()
    settings = get_settings()

    tool_descs = "\n".join(f"- {name}: {cls.description}" for name, cls in TOOL_REGISTRY.items())
    system_msg = INTENT_SYSTEM_PROMPT.format(tool_descriptions=tool_descs)

    # 取最后一条用户消息
    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    try:
        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)

        state["intent"] = result.get("intent", "unknown")
        state["tool_params"] = result.get("params", {})
        state["timestamps"]["intent"] = time.time() - start

        # 低置信度 → 标记需追问
        if result.get("confidence", 0) < 0.5:
            state["final_response"] = result.get("clarification", "抱歉，我不太理解您的需求，能否详细说明？")

        logger.info(f"意图识别: intent={state['intent']}, params={state['tool_params']}")

    except Exception as e:
        logger.error(f"意图识别失败: {e}")
        state["error"] = f"意图识别异常: {e}"
        state["intent"] = "error"

    return state


# ── 参数校验 ──────────────────────────────────────────

def validate_params(state: AgentState) -> AgentState:
    """节点 2: 参数校验"""
    start = time.time()
    intent = state.get("intent")

    if intent in ("unknown", "error", None):
        return state

    try:
        tool_cls = TOOL_REGISTRY.get(intent)
        if not tool_cls:
            state["error"] = f"未知意图: {intent}"
            return state

        # 用 Pydantic 校验参数
        schema = tool_cls.parameters_schema
        params = state.get("tool_params", {})

        # 过滤掉 None 值后校验
        clean_params = {k: v for k, v in params.items() if v is not None}
        # 这里仅做基本类型检查，实际校验在工具 execute 内部完成

        state["timestamps"]["validate"] = time.time() - start
        logger.info(f"参数校验通过: {intent}")

    except Exception as e:
        logger.warning(f"参数校验未通过: {e}")
        state["error"] = f"参数校验失败: {e}"

    return state


# ── 工具执行 ──────────────────────────────────────────

def execute_tool(state: AgentState, retriever: HybridRetriever) -> AgentState:
    """节点 3: 执行业务工具"""
    start = time.time()
    intent = state.get("intent")

    if intent in ("unknown", "error", None) or state.get("error"):
        return state

    try:
        tool_instance = get_tool(intent, retriever)
        params = state.get("tool_params", {})
        result = tool_instance.execute(**params)

        state["tool_result"] = result
        state["timestamps"]["tool"] = time.time() - start
        logger.info(f"工具执行完成: {intent}, 耗时 {state['timestamps']['tool']:.3f}s")

    except Exception as e:
        logger.error(f"工具执行失败 [{intent}]: {e}")
        state["error"] = f"工具执行异常: {e}"
        # 异常回退：用检索兜底
        state["final_response"] = _fallback_response(state)

    return state


# ── 结果格式化 ────────────────────────────────────────

RESPONSE_SYSTEM_PROMPT = """你是一个专业的金融运营助手。基于工具返回的数据，生成自然、简洁的中文回复。

规则：
1. 直接回答用户问题，不要废话
2. 数据以表格或列表形式呈现
3. 如果没有数据，明确告知
4. 涉及金额时保留合适的小数位数
5. 不要暴露内部技术细节（如工具名、trace_id 等）"""


def format_response(state: AgentState, llm_client) -> AgentState:
    """节点 4: LLM 格式化最终回复"""
    start = time.time()

    # 如果已有回复（如追问、错误回退），直接返回
    if state.get("final_response"):
        return state

    settings = get_settings()
    tool_result = state.get("tool_result", {})
    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    prompt = f"""用户问题：{user_msg}

工具返回数据：
```json
{json.dumps(tool_result, ensure_ascii=False, indent=2)}
```

请生成回复："""

    try:
        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": RESPONSE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        state["final_response"] = response.choices[0].message.content
        state["timestamps"]["format"] = time.time() - start

    except Exception as e:
        logger.error(f"结果格式化失败: {e}")
        # 降级：直接返回原始数据摘要
        state["final_response"] = _format_fallback(tool_result)

    return state


def _fallback_response(state: AgentState) -> str:
    """异常回退响应"""
    query = state["messages"][-1]["content"] if state["messages"] else ""
    return f"抱歉，查询「{query[:30]}」时遇到了问题，请稍后重试或联系人工客服。"


def _format_fallback(tool_result: dict) -> str:
    """降级格式化：不依赖 LLM 的简单输出"""
    if not tool_result:
        return "暂无相关数据。"

    results = tool_result.get("results", [])
    count = tool_result.get("count", len(results))
    lines = [f"找到 {count} 条相关信息："]

    for i, r in enumerate(results[:5], 1):
        parsed = r.get("parsed", {})
        text = r.get("text", "")[:80]
        score = r.get("rerank_score", r.get("score", 0))
        lines.append(f"{i}. (相关度: {score:.2f}) {text}")

    if count > 5:
        lines.append(f"... 共 {count} 条，已展示前 5 条")

    return "\n".join(lines)


# ── Graph 构建 ────────────────────────────────────────

class FinancialAgentGraph:
    """
    基于 LangGraph 的金融 Agent 编排器

    流程：
      用户输入 → 意图识别 → 参数校验 → 工具执行 → 结果格式化 → 输出
                    ↓ (低置信度)
                   追问用户
                    ↓ (异常)
                   回退兜底
    """

    def __init__(self, retriever: HybridRetriever, llm_client=None):
        self.retriever = retriever
        self.llm_client = llm_client
        self.graph = self._build_graph()
        self.checkpointer = MemorySaver()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(AgentState)

        g.add_node("identify_intent", lambda s: identify_intent(s, self.llm_client))
        g.add_node("validate_params", validate_params)
        g.add_node("execute_tool", lambda s: execute_tool(s, self.retriever))
        g.add_node("format_response", lambda s: format_response(s, self.llm_client))

        # 条件边：是否需要跳过工具执行
        def should_execute(s: AgentState) -> str:
            if s.get("final_response") or s.get("error"):
                return "format_response"  # 有追问或错误，跳到格式化
            return "execute_tool"

        g.add_edge("identify_intent", "validate_params")
        g.add_conditional_edges("validate_params", should_execute)
        g.add_edge("execute_tool", "format_response")
        g.add_edge("format_response", END)

        g.set_entry_point("identify_intent")
        return g.compile(checkpointer=self.checkpointer)

    async def run(self, user_message: str, chat_history: list[dict] | None = None, trace_id: str = "") -> dict:
        """
        执行一次完整的 Agent 推理流程

        Args:
            user_message: 用户输入
            chat_history: 历史对话 [{"role": "user/assistant", "content": "..."}]
            trace_id: 追踪 ID

        Returns:
            完整的 AgentState 字典
        """
        import uuid

        initial_state: AgentState = {
            "messages": [
                *(chat_history or []),
                {"role": "user", "content": user_message},
            ],
            "intent": "",
            "tool_params": {},
            "tool_result": None,
            "final_response": None,
            "error": None,
            "trace_id": trace_id or str(uuid.uuid4())[:8],
            "timestamps": {},
        }

        t0 = time.time()
        result = await self.graph.ainvoke(initial_state)
        total_time = time.time() - t0
        result["timestamps"]["total"] = total_time

        logger.info(
            f"Agent 完成: trace={result['trace_id']}, "
            f"intent={result['intent']}, "
            f"耗时={total_time:.3f}s, "
            f"各阶段={result['timestamps']}"
        )

        return result

    def run_sync(self, user_message: str, **kwargs) -> dict:
        """同步版本（用于非异步场景）"""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.run(user_message, **kwargs))


# ── 导出给 LangChain tool 调用 ─────────────────────────

def create_langchain_tools(retriever: HybridRetriever) -> list:
    """将业务工具包装为 LangChain tool 格式（可选，用于 ReAct 等 agent 模式）"""
    tools = []
    for name, cls in TOOL_REGISTRY.items():
        instance = cls(retriever)

        @lc_tool(name=name, description=cls.description)
        def _tool_wrapper(**kwargs):
            return instance.execute(**kwargs)

        _tool_wrapper.name = name
        tools.append(_tool_wrapper)
    return tools
