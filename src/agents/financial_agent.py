"""LangGraph 多工具 Agent 引擎 — 意图识别 → 工具调用 → 结果输出"""

from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from langchain_core.tools import tool as lc_tool
from langgraph.graph import END, StateGraph
from loguru import logger

from src.config.settings import get_settings
from src.retrieval.hybrid_retriever import HybridRetriever
from src.tools.business_tools import (
    TOOL_REGISTRY,
    BaseTool,
    get_tool,
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
{{
  "intent": "工具名称",
  "confidence": 0.0-1.0,
  "params": {{
    "参数名": "参数值或null",
    ...
  }},
  "clarification": "如果信息不足需要追问的问题，否则为null"
}}

规则：
1. 如果用户问题与任何工具都不匹配，intent 设为 "unknown"
2. confidence < 0.5 时必须设置 clarification 进行追问
3. 尽量从用户输入中提取所有可能的参数值
4. 参数值为 null 表示用户未提供"""


def _response_content(response: Any) -> str:
    """Read text from either our dict response or an OpenAI-style object."""
    if isinstance(response, dict):
        return str(response["choices"][0]["message"]["content"])
    return str(response.choices[0].message.content)


async def identify_intent(state: AgentState, llm_client) -> AgentState:
    """节点 1: 意图识别 + 参数提取"""
    start = time.time()
    settings = get_settings()

    tool_descs = "\n".join(f"- {name}: {cls.description}" for name, cls in TOOL_REGISTRY.items())
    system_msg = INTENT_SYSTEM_PROMPT.format(tool_descriptions=tool_descs)

    # 取最后一条用户消息
    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    try:
        response = await llm_client.chat_completions_create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        result = json.loads(_response_content(response))
        if not isinstance(result, dict):
            raise ValueError("意图响应必须是 JSON 对象")

        intent = result.get("intent", "unknown")
        state["intent"] = intent if intent in TOOL_REGISTRY else "unknown"
        params = result.get("params", {})
        state["tool_params"] = params if isinstance(params, dict) else {}
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

        params = state.get("tool_params", {})
        if not isinstance(params, dict):
            raise TypeError("工具参数必须是 JSON 对象")

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


async def format_response(state: AgentState, llm_client) -> AgentState:
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
        response = await llm_client.chat_completions_create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": RESPONSE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        state["final_response"] = _response_content(response)
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

    def _build_graph(self) -> StateGraph:
        g = StateGraph(AgentState)

        async def identify_node(state: AgentState) -> AgentState:
            return await identify_intent(state, self.llm_client)

        async def format_node(state: AgentState) -> AgentState:
            return await format_response(state, self.llm_client)

        g.add_node("identify_intent", identify_node)
        g.add_node("validate_params", validate_params)
        g.add_node("execute_tool", lambda s: execute_tool(s, self.retriever))
        g.add_node("format_response", format_node)

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
        return g.compile()

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
        def create_wrapper(tool_name: str, tool_class: type[BaseTool]):
            instance = tool_class(retriever)

            @lc_tool(
                tool_name,
                description=tool_class.description,
                args_schema=tool_class.parameters_schema or {"type": "object", "additionalProperties": True},
            )
            def tool_wrapper(**kwargs):
                return instance.execute(**kwargs)

            return tool_wrapper

        tools.append(create_wrapper(name, cls))
    return tools
