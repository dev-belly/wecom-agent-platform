"""Failure injection and deterministic interleaving over the actual index code.

The small vector backend implements only Chroma's collection protocol, so no
model files, CUDA or network are needed to exercise generation/cleanup behavior.
"""

import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.parsers.pdf_parser import ParsedDocument, ParsedTable
from src.retrieval.hybrid_retriever import HybridRetriever
from src.tools.business_tools import ContractQueryTool, CustomerHoldingTool


def document(name, customer, values):
    return ParsedDocument(name, 1, [ParsedTable(1, 0, [], [
        {"合同编号": f"{customer}-{index}", "客户编号": customer, "产品代码": f"{index:06}",
         "持仓市值": value, "币种": "CNY"}
        for index, value in enumerate(values)
    ])])


class VectorClient:
    def __init__(self):
        self.collections = {}
        self.fail_encode = False
        self.fail_upsert = False
        self.fail_delete = False

    def create_collection(self, name, **kwargs):
        assert name not in self.collections
        collection = VectorCollection(self, name)
        self.collections[name] = collection
        return collection

    def delete_collection(self, name):
        if self.fail_delete:
            self.fail_delete = False
            raise RuntimeError("simulated cleanup unavailable")
        del self.collections[name]


class VectorCollection:
    def __init__(self, client, name):
        self.client, self.name = client, name
        self.records = {}

    def upsert(self, ids, embeddings, documents, metadatas):
        # Simulate a write that fails after changing its target collection.
        self.records[ids[0]] = (documents[0], metadatas[0])
        if self.client.fail_upsert:
            self.client.fail_upsert = False
            raise RuntimeError("simulated partial vector write")
        self.records.update({key: (text, metadata) for key, text, metadata in zip(ids, documents, metadatas)})

    def count(self):
        assert self.name in self.client.collections, "a live reader's collection was deleted"
        return len(self.records)

    def query(self, query_embeddings, n_results, include):
        self.count()
        items = list(self.records.items())[:n_results]
        return {"ids": [[key for key, _ in items]],
                "documents": [[record[0] for _, record in items]],
                "metadatas": [[record[1] for _, record in items]],
                "distances": [[0.0 for _ in items]]}


@pytest.fixture
def vector_client(monkeypatch, tmp_path):
    client = VectorClient()

    class Encoder:
        def __init__(self, model, device):
            pass

        def encode(self, texts, normalize_embeddings):
            if client.fail_encode:
                client.fail_encode = False
                raise RuntimeError("simulated encoder unavailable")
            return np.ones((len(texts), 2))

    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(Client=lambda settings: client, Settings=lambda **kwargs: None))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder))
    monkeypatch.setitem(sys.modules, "FlagEmbedding", None)
    retriever = HybridRetriever()
    monkeypatch.setattr(retriever.settings, "chroma_persist_dir", str(tmp_path / "vectors"))
    return client, retriever


@pytest.mark.parametrize("stage", ["encode", "upsert", "reranker"])
def test_failed_rebuild_preserves_one_complete_generation(vector_client, monkeypatch, stage):
    client, retriever = vector_client
    revision = retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00"])])
    old_names = set(client.collections)
    if stage == "reranker":
        monkeypatch.setattr(retriever, "_load_reranker", lambda snapshot: (_ for _ in ()).throw(RuntimeError("reranker unavailable")))
    else:
        setattr(client, f"fail_{stage}", True)
    with pytest.raises(RuntimeError):
        retriever.build_index_from_parsed([document("new.pdf", "NEW", ["20.00", "30.00"])])
    assert retriever.index_revision == revision
    assert set(client.collections) == old_names
    assert CustomerHoldingTool(retriever).execute(customer_id="OLD")["total_value"] == "10.00"
    assert CustomerHoldingTool(retriever).execute(customer_id="NEW")["count"] == 0
    assert {item["metadata"]["source"] for item in retriever.retrieve("合同")} == {"old.pdf"}


def test_failed_initial_build_never_claims_ready_and_discards_partial_vectors(vector_client):
    client, retriever = vector_client
    client.fail_upsert = True
    with pytest.raises(RuntimeError):
        retriever.build_index_from_parsed([document("new.pdf", "NEW", ["20.00"])])
    assert not retriever._initialized
    assert retriever.index_revision is None
    assert client.collections == {}
    with pytest.raises(RuntimeError, match="索引未初始化"):
        retriever.retrieve("NEW")


def test_shrinking_corpus_has_no_old_tail_and_repeated_rebuilds_keep_one_collection(vector_client):
    client, retriever = vector_client
    # A legacy/user-owned collection must not be deleted by a broad cleanup.
    legacy = client.create_collection(retriever.settings.collection_name)
    legacy.records["legacy"] = ("private older data", {})
    for count in (3, 1, 5, 1):
        retriever.build_index_from_parsed([document(f"new-{count}.pdf", "NEW", ["1.00"] * count)])
        assert len(client.collections) == 2  # Current generation plus untouched legacy.
        assert retriever.collection.count() == count
        assert len(retriever.bm25_docs) == count
        assert CustomerHoldingTool(retriever).execute(customer_id="NEW")["total_value"] == f"{count}.00"
        assert {item["metadata"]["source"] for item in retriever.retrieve("合同", top_k=10)} == {f"new-{count}.pdf"}
    retriever.close()
    assert client.collections == {legacy.name: legacy}


def test_retrieval_pins_generation_through_bm25_vector_and_reranking(vector_client, monkeypatch):
    client, retriever = vector_client
    retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00", "11.00"])])
    old_name = retriever.collection.name
    started, release = Event(), Event()
    bm25_search = retriever._bm25_search

    def pause_after_bm25(query, top_k, snapshot=None):
        results = bm25_search(query, top_k, snapshot)
        started.set()
        assert release.wait(timeout=5)
        return results

    monkeypatch.setattr(retriever, "_bm25_search", pause_after_bm25)
    with ThreadPoolExecutor(max_workers=1) as executor:
        query = executor.submit(retriever.retrieve, "合同", 10)
        try:
            assert started.wait(timeout=5)
            retriever.build_index_from_parsed([document("new.pdf", "NEW", ["20.00"])])
            assert old_name in client.collections  # Reader has not reached vector search yet.
        finally:
            release.set()
        assert {item["metadata"]["source"] for item in query.result(timeout=5)} == {"old.pdf"}
    assert old_name not in client.collections
    assert len(client.collections) == 1
    assert {item["metadata"]["source"] for item in retriever.retrieve("合同")} == {"new.pdf"}


def test_business_query_keeps_all_rows_from_its_captured_generation(vector_client, monkeypatch):
    from src.tools import business_tools

    _, retriever = vector_client
    revision = retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00", "11.00"])])
    normalize = business_tools.normalize_row
    calls = 0

    def replace_between_rows(row):
        nonlocal calls
        calls += 1
        if calls == 1:
            retriever.build_index_from_parsed([document("new.pdf", "OLD", ["100.00"])])
        return normalize(row)

    monkeypatch.setattr(business_tools, "normalize_row", replace_between_rows)
    result = CustomerHoldingTool(retriever).execute(customer_id="OLD")
    assert result["total_value"] == "21.00"
    assert result["index_revision"] == revision
    assert result["index_revision"] != retriever.index_revision
    assert {item["metadata"]["source"] for item in result["results"]} == {"old.pdf"}
    assert CustomerHoldingTool(retriever).execute(customer_id="OLD")["total_value"] == "100.00"


def test_empty_business_result_still_identifies_its_captured_generation(vector_client):
    _, retriever = vector_client
    revision = retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00"])])
    assert ContractQueryTool(retriever).execute(contract_id="MISSING")["index_revision"] == revision
    assert CustomerHoldingTool(retriever).execute(customer_id="MISSING")["index_revision"] == revision


def test_close_defers_collection_deletion_until_captured_reader_finishes(vector_client):
    client, retriever = vector_client
    retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00"])])
    with retriever.read_snapshot() as snapshot:
        retriever.close()
        assert not retriever._initialized
        assert snapshot.collection.count() == 1
    assert client.collections == {}
    with pytest.raises(RuntimeError, match="已关闭"):
        retriever.build_index_from_parsed([document("new.pdf", "NEW", ["20.00"])])
    assert client.collections == {}


def test_cleanup_failure_is_visible_and_retried_on_next_rebuild(vector_client):
    client, retriever = vector_client
    retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00"])])
    client.fail_delete = True
    retriever.build_index_from_parsed([document("new.pdf", "NEW", ["20.00"])])
    assert retriever.index_status()["cleanup_pending"] == 1
    assert len(client.collections) == 2
    retriever.build_index_from_parsed([document("latest.pdf", "LATEST", ["30.00"])])
    assert retriever.index_status()["cleanup_pending"] == 0
    assert len(client.collections) == 1


def test_failed_rebuild_http_response_reports_preserved_revision(vector_client):
    import src.main as main

    client, retriever = vector_client
    revision = retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00"])])
    client.fail_upsert = True
    api = TestClient(main.app)  # No lifespan/model warmup.
    with patch.object(main, "retriever", retriever), patch.object(main.settings, "api_key", ""), patch.object(main.settings, "env", "development"), patch.object(main.FinancialPDFParser, "parse_all", return_value=[document("new.pdf", "NEW", ["20.00"])]):
        response = api.post("/api/index/build", json={"force_rebuild": True})
        assert response.status_code == 503
        assert response.json()["detail"]["index_preserved"]
        assert response.json()["detail"]["index_revision"] == revision
        assert api.get("/api/index/status").json()["index_revision"] == revision
        assert api.post("/api/holdings/query", json={"customer_id": "OLD"}).json()["total_value"] == "10.00"
    api.close()


def test_skipped_rebuild_is_explicit_and_does_not_claim_new_documents_are_indexed(vector_client):
    import src.main as main

    _, retriever = vector_client
    revision = retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00"])])
    api = TestClient(main.app)
    with patch.object(main, "retriever", retriever), patch.object(main.settings, "api_key", ""), patch.object(main.settings, "env", "development"), patch.object(main.FinancialPDFParser, "parse_all", return_value=[document("new.pdf", "NEW", ["20.00"])]):
        body = api.post("/api/index/build", json={"force_rebuild": False}).json()
    api.close()
    assert body["status"] == "unchanged"
    assert not body["index_rebuilt"]
    assert body["index_revision"] == revision
    assert ContractQueryTool(retriever).execute(contract_id="NEW-0")["count"] == 0


def test_actual_chroma_generations_and_cleanup_when_optional_dependency_is_installed(monkeypatch, tmp_path):
    pytest.importorskip("chromadb", reason="optional Chroma persistence smoke; no embedding models required")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")

    class Encoder:
        def __init__(self, model, device):
            pass

        def encode(self, texts, normalize_embeddings):
            return np.ones((len(texts), 2))

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder))
    monkeypatch.setitem(sys.modules, "FlagEmbedding", None)
    retriever = HybridRetriever()
    monkeypatch.setattr(retriever.settings, "chroma_persist_dir", str(tmp_path / "actual-vectors"))
    retriever.build_index_from_parsed([document("old.pdf", "OLD", ["10.00", "11.00", "12.00"])])
    with retriever.read_snapshot() as old:
        client = old.chroma_client
        retriever.build_index_from_parsed([document("new.pdf", "NEW", ["20.00"])])
        assert old.collection.count() == 3
        assert retriever.collection.count() == 1
        assert client.count_collections() == 2
        assert {item["metadata"]["source"] for item in retriever.retrieve("合同")} == {"new.pdf"}
    assert client.count_collections() == 1
    revision = retriever.index_revision
    with patch.object(retriever, "_load_reranker", side_effect=RuntimeError("injected failure after persistent write")):
        with pytest.raises(RuntimeError):
            retriever.build_index_from_parsed([document("failed.pdf", "FAILED", ["40.00"])])
    assert retriever.index_revision == revision
    assert client.count_collections() == 1
    retriever.close()
    assert client.count_collections() == 0
