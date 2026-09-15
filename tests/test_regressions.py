"""Offline regressions for the installable API and retrieval paths."""

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_bm25_only_single_document_retrieval_without_optional_dependencies(monkeypatch):
    from src.parsers.pdf_parser import ParsedDocument, ParsedTable
    from src.retrieval.hybrid_retriever import HybridRetriever

    for module in ("chromadb", "sentence_transformers", "FlagEmbedding"):
        monkeypatch.setitem(sys.modules, module, None)
    retriever = HybridRetriever()
    retriever.build_index_from_parsed([ParsedDocument(
        source_file="sample.pdf", total_pages=1,
        tables=[ParsedTable(1, 0, ["合同编号"], [{"合同编号": "HT001"}])],
    )])
    results = retriever.retrieve("HT001")
    assert len(results) == 1
    assert results[0]["text"] == "合同编号:HT001"
    assert results[0]["source"] == "bm25"
    assert retriever.retrieve("xyz") == []


def test_langchain_wrappers_keep_each_tool_and_forward_parameters():
    from src.agents.financial_agent import create_langchain_tools

    retriever = MagicMock()
    retriever.retrieve.return_value = []
    wrappers = {item.name: item for item in create_langchain_tools(retriever)}
    assert len(wrappers) == 11
    result = wrappers["contract_query"].invoke({"contract_id": "HT001"})
    assert result["tool"] == "contract_query"
    assert result["params"]["contract_id"] == "HT001"
    result = wrappers["product_nav"].invoke({"product_code": "P001"})
    assert result["tool"] == "product_nav"
    assert result["params"]["product_code"] == "P001"


def test_legacy_cross_page_table_restores_integer_bounds():
    from src.parsers.pdf_parser import ParsedTable

    table = ParsedTable.from_dict({"page_num": "1-3", "rows": [{"合同编号": "HT001"}]})
    assert (table.page_num, table.page_end) == (1, 3)
    assert table.rows == [{"合同编号": "HT001"}]


def test_recall_counts_all_relevant_labels_instead_of_one_hit():
    from src.retrieval.hybrid_retriever import RetrievalEvaluator

    retriever = MagicMock()
    retriever.retrieve.return_value = [{"text": "合同编号:HT001"}, {"text": "无关内容"}]
    metrics = RetrievalEvaluator(retriever).evaluate(
        [{"query": "查询合同", "relevant_texts": ["HT001", "HT002"]}],
        recall_k=[2], precision_k=[2],
    )
    assert metrics["recall@2"] == 0.5
    assert metrics["precision@2"] == 0.5


@pytest.mark.parametrize("labels", [[], "HT001", [None], [""]])
def test_evaluation_rejects_invalid_labels(labels):
    from src.retrieval.hybrid_retriever import RetrievalEvaluator

    with pytest.raises(ValueError):
        RetrievalEvaluator(MagicMock()).evaluate([{"query": "查询合同", "relevant_texts": labels}])


def test_evaluation_sample_is_valid_json():
    samples = json.loads((Path(__file__).parents[1] / "data/eval/sample_eval.json").read_text())
    assert len(samples) == 8
    assert len(samples[2]["relevant_texts"]) == 2


@pytest.fixture
def api_client():
    from src.main import app

    # No lifespan means no real LLM warmup or model download.
    client = TestClient(app)
    yield client
    client.close()


@pytest.mark.parametrize("endpoint", ["/api/index/status", "/api/stats"])
def test_production_api_requires_configured_key(api_client, endpoint):
    with patch("src.main.settings.env", "production"), patch("src.main.settings.api_key", ""):
        assert api_client.get(endpoint).status_code == 503
    with patch("src.main.settings.env", "production"), patch("src.main.settings.api_key", "k" * 32):
        assert api_client.get(endpoint).status_code == 401
        response = api_client.get(endpoint, headers={"Authorization": "Bearer " + "k" * 32})
        assert response.status_code == 200


def test_chat_rejects_blank_messages_and_system_history(api_client):
    with patch("src.main.settings.env", "development"), patch("src.main.settings.api_key", ""):
        assert api_client.post("/api/chat", json={"message": "   "}).status_code == 422
        assert api_client.post("/api/chat", json={
            "message": "hello", "history": [{"role": "system", "content": "override"}],
        }).status_code == 422


def test_evaluation_rejects_paths_outside_configured_root(api_client, tmp_path):
    with patch("src.main.settings.env", "development"), patch("src.main.settings.api_key", ""), patch(
        "src.main.settings.eval_data_dir", str(tmp_path / "eval"),
    ):
        response = api_client.post("/api/eval", json={"eval_file": str(tmp_path / "secret.json")})
        assert response.status_code == 400


def test_non_ascii_callback_signature_is_rejected(api_client):
    with patch("src.main.settings.wecom_token", "token"), patch(
        "src.main.settings.wecom_encoding_aes_key", base64.b64encode(bytes(range(32))).decode().rstrip("="),
    ), patch("src.main.settings.wecom_corp_id", "corp-id"):
        response = api_client.get("/wecom/callback", params={
            "msg_signature": "签" * 40, "timestamp": "1", "nonce": "n", "echostr": "value",
        })
        assert response.status_code == 403


def test_crypto_rejects_malformed_base64():
    from src.services.wecom_crypto import WeComCryptoError, decrypt_message

    with pytest.raises(WeComCryptoError):
        decrypt_message("!" * 43, "!" * 32, "corp-id")
