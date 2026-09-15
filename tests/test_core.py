"""Core regression tests for parsing, retrieval, agent routing, and API security."""

import base64
import hashlib
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class TestPDFParser:
    def test_field_standardization(self):
        from src.parsers.pdf_parser import FinancialPDFParser

        assert FinancialPDFParser._clean_header("合 同 号") == "合同编号"
        assert FinancialPDFParser._clean_header("合约编号") == "合同编号"
        assert FinancialPDFParser._clean_header("最新净值") == "单位净值"
        assert FinancialPDFParser._clean_header("产品代号") == "产品代码"

    def test_normalize_cell(self):
        from src.parsers.pdf_parser import FinancialPDFParser

        assert FinancialPDFParser._normalize_cell("1,234.56") == 1234.56
        assert FinancialPDFParser._normalize_cell("  100  ") == 100
        assert FinancialPDFParser._normalize_cell(None) is None
        assert FinancialPDFParser._normalize_cell("") is None
        assert FinancialPDFParser._normalize_cell("测试文本") == "测试文本"

    def test_header_similarity(self):
        from src.parsers.pdf_parser import FinancialPDFParser

        h1 = ["合同编号", "甲方", "乙方", "金额"]
        h2 = ["合同编号", "甲方", "乙方", "币种"]
        assert FinancialPDFParser._header_similarity(h1, h2) > 0.5

    def test_cross_page_merge_tracks_the_last_page(self, tmp_path):
        from src.parsers.pdf_parser import FinancialPDFParser, ParsedTable

        tables = [
            ParsedTable(1, 0, ["A", "B"], [{"A": "a1", "B": "b1"}], "test.pdf"),
            ParsedTable(2, 0, ["A", "B"], [{"A": "a2", "B": "b2"}], "test.pdf"),
            ParsedTable(3, 0, ["A", "B"], [{"A": "a3", "B": "b3"}], "test.pdf"),
            ParsedTable(4, 0, ["X", "Y"], [{"X": "x1"}], "test.pdf"),
        ]
        parser = FinancialPDFParser(tmp_path / "in", tmp_path / "out")
        merged = parser._merge_cross_page_tables(tables)

        assert len(merged) == 2
        assert len(merged[0].rows) == 3
        assert merged[0].page_num == 1
        assert merged[0].page_end == 3

    def test_parsed_document_round_trip_keeps_text(self):
        from src.parsers.pdf_parser import ParsedDocument

        original = ParsedDocument(source_file="sample.pdf", total_pages=1, raw_text="真实正文")
        restored = ParsedDocument.from_dict(original.to_dict())
        assert restored.raw_text == "真实正文"


class TestHybridRetriever:
    @pytest.fixture
    def retriever(self):
        from src.retrieval.hybrid_retriever import HybridRetriever

        return HybridRetriever()

    def test_tokenization(self):
        from src.retrieval.hybrid_retriever import HybridRetriever

        tokens = HybridRetriever._tokenize_zh("合同编号HT001")
        assert tokens
        assert any("合同" in token for token in tokens)

    def test_rrf_fusion_uses_a_stable_content_key(self):
        from src.retrieval.hybrid_retriever import HybridRetriever

        results_a = [{"text": "a", "metadata": {"page": 1}}, {"text": "b"}]
        results_b = [{"text": "c"}, {"text": "a", "metadata": {"page": 1}}]
        fused = HybridRetriever._rrf_fusion(results_a, results_b)
        assert fused[0]["text"] == "a"

    def test_rerank_falls_back_when_optional_model_is_absent(self, retriever):
        candidates = [{"text": "a", "rrf_score": 0.2}, {"text": "b", "rrf_score": 0.1}]
        assert retriever._rerank("query", candidates, 1) == [
            {"text": "a", "rrf_score": 0.2, "rerank_score": 0.2},
        ]

    def test_empty_evaluation_is_rejected(self, retriever):
        from src.retrieval.hybrid_retriever import RetrievalEvaluator

        with pytest.raises(ValueError, match="不能为空"):
            RetrievalEvaluator(retriever).evaluate([])


class TestBusinessTools:
    def test_tool_registry_complete(self):
        from src.tools.business_tools import TOOL_REGISTRY

        expected_tools = {
            "contract_query",
            "product_nav",
            "customer_holding",
            "product_info",
            "fee_query",
            "risk_query",
            "custody_bank",
            "fund_manager",
            "risk_factor_query",
            "financial_report_query",
            "factor_mining",
        }
        assert set(TOOL_REGISTRY) == expected_tools
        assert len(TOOL_REGISTRY) == 11

    def test_contract_params_validation(self):
        from src.tools.business_tools import ContractQueryParams

        params = ContractQueryParams(contract_id="HT001", min_amount=1000)
        assert params.contract_id == "HT001"
        assert params.min_amount == 1000

    def test_invalid_min_amount(self):
        from pydantic import ValidationError

        from src.tools.business_tools import ContractQueryParams

        with pytest.raises(ValidationError):
            ContractQueryParams(min_amount=-100)


class TestAgentGraph:
    def test_format_fallback(self):
        from src.agents.financial_agent import _format_fallback

        tool_result = {
            "count": 3,
            "results": [
                {"parsed": {}, "text": "合同:HT001 | 金额:100万", "score": 0.95},
                {"parsed": {}, "text": "合同:HT002 | 金额:200万", "score": 0.85},
                {"parsed": {}, "text": "合同:HT003 | 金额:300万", "score": 0.75},
            ],
        }
        output = _format_fallback(tool_result)
        assert "3 条" in output
        assert "HT001" in output

    @pytest.mark.asyncio
    async def test_async_graph_awaits_llm_and_executes_tool(self):
        from src.agents.financial_agent import FinancialAgentGraph

        retriever = MagicMock()
        retriever.retrieve.return_value = [{"text": "产品代码:P001", "score": 1.0}]
        llm = MagicMock()
        llm.chat_completions_create = AsyncMock(
            side_effect=[
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"intent":"product_info","confidence":0.9,"params":{"product_code":"P001"}}',
                            },
                        },
                    ],
                },
                {"choices": [{"message": {"content": "产品信息已找到"}}]},
            ],
        )

        result = await FinancialAgentGraph(retriever, llm).run("查询 P001")

        assert result["intent"] == "product_info"
        assert result["final_response"] == "产品信息已找到"
        assert llm.chat_completions_create.await_count == 2
        retriever.retrieve.assert_called_once()


class TestSemanticCache:
    def test_cache_hit_miss(self):
        from src.models.llm_client import SemanticCache

        cache = SemanticCache(max_size=10, ttl_seconds=60)
        messages = [{"role": "user", "content": "hello"}]
        assert cache.get("model-a", messages) is None
        cache.set("model-a", messages, "cached response")
        assert cache.get("model-a", messages) == "cached response"

    def test_cache_stats(self):
        from src.models.llm_client import SemanticCache

        cache = SemanticCache(max_size=10, ttl_seconds=60)
        cache.misses += 10
        cache.hits += 5
        assert cache.stats()["hit_rate"] == round(5 / 15, 4)


def _encrypt_wecom_message(key: bytes, message: str, receive_id: str) -> str:
    payload = b"0123456789abcdef" + struct.pack(">I", len(message.encode()))
    payload += message.encode() + receive_id.encode()
    pad_size = 32 - (len(payload) % 32)
    padded = payload + bytes([pad_size]) * pad_size
    encryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()


def test_wecom_signature_and_decryption():
    from src.services.wecom_crypto import decrypt_message, verify_signature

    token = "callback-token"
    timestamp = "1720000000"
    nonce = "nonce"
    key = bytes(range(32))
    encrypted = _encrypt_wecom_message(key, "<xml><Content>hello</Content></xml>", "corp-id")
    signature = hashlib.sha1("".join(sorted((token, timestamp, nonce, encrypted))).encode()).hexdigest()

    assert verify_signature(token, signature, timestamp, nonce, encrypted)
    assert decrypt_message(base64.b64encode(key).decode().rstrip("="), encrypted, "corp-id") == (
        "<xml><Content>hello</Content></xml>"
    )


@pytest.mark.asyncio
async def test_chat_api_flow():
    from fastapi.testclient import TestClient

    from src.main import app

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(
        return_value={
            "final_response": "测试回复",
            "intent": "product_nav",
            "trace_id": "test123",
            "timestamps": {"total": 0.05},
        },
    )
    client = TestClient(app)
    with patch("src.main._app_ready", True), patch("src.main.agent_graph", mock_agent):
        response = client.post("/api/chat", json={"message": "查询净值"})
    client.close()

    assert response.status_code == 200
    assert response.json()["reply"] == "测试回复"
    assert response.json()["intent"] == "product_nav"
