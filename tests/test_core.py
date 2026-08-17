"""核心模块测试"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# ── PDF Parser 测试 ──────────────────────────────────

class TestPDFParser:
    """PDF 解析器测试"""

    def test_field_standardization(self):
        from parsers.pdf_parser import FinancialPDFParser
        assert FinancialPDFParser._clean_header("合 同 号") == "合同编号"
        assert FinancialPDFParser._clean_header("合约编号") == "合同编号"
        assert FinancialPDFParser._clean_header("最新净值") == "单位净值"
        assert FinancialPDFParser._clean_header("产品代号") == "产品代码"

    def test_normalize_cell(self):
        from parsers.pdf_parser import FinancialPDFParser
        assert FinancialPDFParser._normalize_cell("1,234.56") == 1234.56
        assert FinancialPDFParser._normalize_cell("  100  ") == 100
        assert FinancialPDFParser._normalize_cell(None) is None
        assert FinancialPDFParser._normalize_cell("") is None
        assert FinancialPDFParser._normalize_cell("测试文本") == "测试文本"

    def test_header_similarity(self):
        from parsers.pdf_parser import FinancialPDFParser
        h1 = ["合同编号", "甲方", "乙方", "金额"]
        h2 = ["合同编号", "甲方", "乙方", "币种"]
        sim = FinancialPDFParser._header_similarity(h1, h2)
        assert sim > 0.5  # 3/5 相同

    def test_cross_page_merge(self):
        from parsers.pdf_parser import FinancialPDFParser, ParsedTable
        tables = [
            ParsedTable(page_num=1, table_index=0, headers=["A", "B"],
                       rows=[{"A": "a1", "B": "b1"}], source_file="test.pdf"),
            ParsedTable(page_num=2, table_index=0, headers=["A", "B"],
                       rows=[{"A": "a2", "B": "b2"}], source_file="test.pdf"),
            ParsedTable(page_num=3, table_index=0, headers=["X", "Y"],
                       rows=[{"X": "x1"}], source_file="test.pdf"),  # 不同 header，不合并
        ]
        parser = FinancialPDFParser("/tmp/in", "/tmp/out")
        merged = parser._merge_cross_page_tables(tables)
        # 前 2 个应合并为 1 个
        assert len(merged) == 2
        assert len(merged[0].rows) == 2


# ── Retrieval 测试 ────────────────────────────────────

class TestHybridRetriever:
    """混合检索器测试"""

    @pytest.fixture
    def retriever(self):
        from retrieval.hybrid_retriever import HybridRetriever
        r = HybridRetriever()
        return r

    def test_tokenization(self):
        from retrieval.hybrid_retriever import HybridRetriever
        tokens = HybridRetriever._tokenize_zh("合同编号HT001")
        assert len(tokens) > 0
        assert any("合同" in t for t in tokens)

    def test_rrf_fusion(self):
        from retrieval.hybrid_retriever import HybridRetriever
        results_a = [{"text": "a"}, {"text": "b"}]
        results_b = [{"text": "c"}, {"text": "a"}]
        fused = HybridRetriever._rrf_fusion(results_a, results_b)
        # "a" 在两个结果集中都有，应该排第一
        assert fused[0]["text"] == "a"


# ── Tools 测试 ────────────────────────────────────────

class TestBusinessTools:
    """业务工具测试"""

    def test_tool_registry_complete(self):
        from tools.business_tools import TOOL_REGISTRY
        expected_tools = [
            "contract_query", "product_nav", "customer_holding",
            "product_info", "fee_query", "risk_query",
            "custody_bank", "fund_manager",
        ]
        assert set(TOOL_REGISTRY.keys()) == set(expected_tools)
        assert len(TOOL_REGISTRY) == 8

    def test_contract_params_validation(self):
        from tools.business_tools import ContractQueryParams
        params = ContractQueryParams(contract_id="HT001", min_amount=1000)
        assert params.contract_id == "HT001"
        assert params.min_amount == 1000

    def test_invalid_min_amount(self):
        from tools.business_tools import ContractQueryParams
        with pytest.raises(Exception):  # Pydantic ValidationError
            ContractQueryParams(min_amount=-100)


# ── Agent 测试 ────────────────────────────────────────

class TestAgentGraph:
    """Agent 图测试"""

    def test_format_fallback(self):
        from agents.financial_agent import _format_fallback
        tool_result = {
            "count": 3,
            "results": [
                {"parsed": {}, "text": "合同:HT001 | 金额:100万", "score": 0.95},
                {"parsed": {}, "text": "合同:HT002 | 金额:200万", "score": 0.85},
                {"parsed": {}, "text": "合同:HT003 | 金额:300万", "score": 0.75},
                {"parsed": {}, "text": "合同:HT004", "score": 0.60},
                {"parsed": {}, "text": "合同:HT005", "score": 0.55},
            ],
        }
        output = _format_fallback(tool_result)
        assert "3 条" in output
        assert "HT001" in output


# ── LLM Client 测试 ──────────────────────────────────

class TestSemanticCache:
    """语义缓存测试"""

    def test_cache_hit_miss(self):
        from models.llm_client import SemanticCache
        cache = SemanticCache(max_size=10, ttl_seconds=60)

        messages = [{"role": "user", "content": "hello"}]
        assert cache.get("model-a", messages) is None
        cache.set("model-a", messages, "cached response")
        assert cache.get("model-a", messages) == "cached response"

    def test_cache_stats(self):
        from models.llm_client import SemanticCache
        cache = SemanticCache(max_size=10, ttl_seconds=60)
        cache.misses += 10
        cache.hits += 5
        stats = cache.stats()
        assert stats["hit_rate"] == round(5 / 15, 4)


# ── 集成测试（Mock LLM）─ ─────────────────────────────

@pytest.mark.asyncio
async def test_chat_api_flow():
    """端到端聊天流程测试（Mock）"""
    from fastapi.testclient import TestClient
    from src.main import app

    client = TestClient(app)

    # Mock retriever 和 agent
    with patch("src.main.agent_graph") as mock_agent:
        mock_agent.run = AsyncMock(return_value={
            "final_response": "测试回复",
            "intent": "product_nav",
            "trace_id": "test123",
            "timestamps": {"total": 0.05},
        })

        resp = client.post("/api/chat", json={"message": "查询净值"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "测试回复"
        assert data["intent"] == "product_nav"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
