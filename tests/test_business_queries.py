"""Offline business cases over real-shaped Chinese parser/index/API records.

All records are fictional. Tests use the actual BM25 index ingestion, tools and
HTTP routes; no model, vector dependency, download or external account is used.
"""

import sys
from decimal import Decimal, Inexact, Overflow, Rounded, localcontext
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.parsers.pdf_parser import FinancialPDFParser, ParsedDocument, ParsedTable
from src.retrieval.hybrid_retriever import HybridRetriever
from src.tools.business_tools import (
    ContractQueryParams,
    ContractQueryTool,
    CustomerHoldingTool,
)
from src.tools.structured_records import normalize_row, parse_money


@pytest.fixture
def build_index(monkeypatch):
    for module in ("chromadb", "sentence_transformers", "FlagEmbedding"):
        monkeypatch.setitem(sys.modules, module, None)

    def build(rows):
        # Preserve the field-aware conversion that parse_single actually uses.
        parsed_rows = [{
            FinancialPDFParser._clean_header(key): FinancialPDFParser._normalize_cell(value, header=FinancialPDFParser._clean_header(key))
            for key, value in row.items()
        } for row in rows]
        retriever = HybridRetriever()
        retriever.build_index_from_parsed([ParsedDocument(
            source_file="fictional_business.pdf", total_pages=3,
            tables=[ParsedTable(2, 0, list(parsed_rows[0]), parsed_rows, page_end=3)],
            raw_text="正文中提到其他客户或合同，但正文不是结构化业务记录，不能作为汇总依据。",
        )])
        # A structured query must never silently become a ranked sample.
        retriever.retrieve = MagicMock(side_effect=AssertionError("business queries cannot use top-k retrieval"))
        return retriever

    return build


def contract(contract_id="HT001", **overrides):
    return {"合同编号": contract_id, "甲方": "示例银行股份有限公司", "乙方": "示例基金管理有限公司",
            "签约日期": "2024-03-15", "合同金额": "1,000.10", "币种": "CNY", **overrides}


def holding(product_code="001234", **overrides):
    return {"客户编号": "C10086", "客户姓名": "张三", "产品代码": product_code,
            "持仓份额": "100", "持仓市值": "0.10", "币种": "CNY", **overrides}


def test_contract_id_does_not_match_similar_ids_or_a_prose_mention(build_index):
    retriever = build_index([contract("HT0010"), contract("HT001"), contract("OTHER", 合同名称="与 HT001 相关的合同")])
    result = ContractQueryTool(retriever).execute(contract_id="HT001")
    assert result["count"] == 1
    assert result["results"][0]["parsed"]["contract_id"] == "HT001"
    assert result["results"][0]["metadata"] == {
        "source": "fictional_business.pdf", "type": "table_row", "page": 2,
        "page_end": 3, "table_index": 0, "row_index": 1,
    }


def test_contract_all_predicates_are_anded_and_dates_are_inclusive(build_index):
    rows = [
        contract("START", 签约日期="2024年01月01日"),
        contract("END", 签约日期="2024/12/31"),
        contract("WRONG_PARTY", 甲方="另一家机构"),
        contract("WRONG_COUNTERPARTY", 乙方="另一家基金"),
        contract("OLD", 签约日期="2023-12-31"),
        contract("NEW", 签约日期="2025-01-01"),
        contract("MISSING", 签约日期=""),
        contract("INVALID", 签约日期="2024-02-30"),
    ]
    result = ContractQueryTool(build_index(rows)).execute(
        party_a="示例银行", party_b="示例基金", date_range_start="2024-01-01", date_range_end="2024-12-31",
    )
    assert {r["parsed"]["contract_id"] for r in result["results"]} == {"START", "END"}


def test_amount_filter_uses_units_currency_and_exact_decimal_not_relevance(build_index):
    rows = [contract(f"NOISE-{i}", 合同金额="999.99") for i in range(60)]
    rows += [
        contract("YEN", 合同金额="100000000", 币种="JPY"),
        contract("UNKNOWN", 合同金额="100000000", 币种=""),
        contract("INVALID", 合同金额="约 1000 万"),
        contract("BOUNDARY", 合同金额="1,000.10"),
        contract("UNIT", 合同金额="0.10002万元"),
    ]
    result = ContractQueryTool(build_index(rows)).execute(min_amount="1000.10", currency="RMB")
    assert {r["parsed"]["contract_id"] for r in result["results"]} == {"BOUNDARY", "UNIT"}
    assert {r["amount"] for r in result["results"]} == {"1000.10", "1000.20000"}
    assert result["params"]["min_amount"] == "1000.10"
    assert result["params"]["currency"] == "CNY"


@pytest.mark.parametrize("params", [
    {"min_amount": "1"},
    {"min_amount": "NaN", "currency": "CNY"},
    {"date_range_start": "2025-01-01", "date_range_end": "2024-01-01"},
    {"contract_id": " "},
    {"max_amount": "1000"},
])
def test_invalid_business_filters_fail_before_querying(params):
    with pytest.raises(ValidationError):
        ContractQueryParams(**params)


def test_contract_count_covers_full_table_beyond_display_limit(build_index):
    result = ContractQueryTool(build_index([contract(f"HT{i}") for i in range(25)])).execute()
    assert result["count"] == 25
    assert len(result["results"]) == result["returned_count"] == 10
    assert result["truncated"]


def test_holding_exact_identity_and_product_preserve_leading_zero(build_index):
    retriever = build_index([
        holding(持仓市值="1,000.10"), holding("001235", 持仓市值="5.00"),
        holding(客户编号="OTHER", 客户姓名="张三丰", 持仓市值="99999999"),
    ])
    result = CustomerHoldingTool(retriever).execute(customer_name="张三", customer_id="C10086", product_code="001234")
    assert result["count"] == 1
    assert result["results"][0]["parsed"]["product_code"] == "001234"
    assert result["total_value"] == "1000.10"
    assert result["total_currency"] == "CNY"
    assert result["total_value_by_currency"] == {"CNY": "1000.10"}
    assert result["totals_complete"]


def test_holding_sum_covers_all_rows_before_display_truncation(build_index):
    result = CustomerHoldingTool(build_index([holding(f"{i:06}", 持仓市值="0.10") for i in range(25)])).execute(customer_id="C10086")
    assert result["count"] == 25
    assert len(result["results"]) == 20
    assert result["total_value"] == "2.50"
    assert result["truncated"]
    assert result["query_scope"] == "all_indexed_table_rows"


def test_holding_money_never_rounds_through_float(build_index):
    result = CustomerHoldingTool(build_index([
        holding("000001", 持仓市值="9007199254740993.01"),
        holding("000002", 持仓市值="0.02"),
    ])).execute(customer_id="C10086")
    assert result["total_value"] == "9007199254740993.03"


def test_money_arithmetic_does_not_inherit_a_callers_decimal_context(build_index):
    tool = CustomerHoldingTool(build_index([
        holding("000001", 持仓市值="9007199254740993.01"),
        holding("000002", 持仓市值="0.02"),
    ]))
    with localcontext() as hostile:
        hostile.prec = 2
        hostile.Emax = 2
        hostile.Emin = -2
        for signal in (Overflow, Inexact, Rounded):
            hostile.traps[signal] = True
        amount, currency = parse_money("1.001万元", "CNY")
        assert amount == Decimal("10010.000")
        assert currency == "CNY"
        assert tool.execute(customer_id="C10086")["total_value"] == "9007199254740993.03"


def test_holding_currencies_are_separate_without_invented_fx(build_index):
    result = CustomerHoldingTool(build_index([
        holding(持仓市值="1.01"), holding("000002", 持仓市值="USD 2.02", 币种="USD"),
    ])).execute(customer_id="C10086")
    assert result["total_value"] is None
    assert result["total_value_by_currency"] == {"CNY": "1.01", "USD": "2.02"}
    assert result["totals_complete"]
    assert "未进行汇率换算" in result["warnings"][0]


@pytest.mark.parametrize("missing", [
    {"持仓市值": "待估值"}, {"持仓市值": ""}, {"币种": ""},
    {"持仓市值": "100美元"}, {"持仓市值": "1,00"},
])
def test_incomplete_holding_is_not_silently_zero_or_a_full_total(build_index, missing):
    result = CustomerHoldingTool(build_index([holding(持仓市值="1.00"), holding("000002", **missing)])).execute(customer_id="C10086")
    assert result["count"] == 2
    assert result["total_value"] is None
    assert result["total_value_by_currency"] == {"CNY": "1.00"}
    assert not result["totals_complete"]
    assert result["unpriced_count"] == 1
    assert result["warnings"]
    assert result["results"][1]["amount_error"]


def test_header_unit_is_preserved_and_explicitly_scaled(build_index):
    row = holding()
    row.pop("持仓市值")
    row["持有市值（万元）"] = "1.000001"
    result = CustomerHoldingTool(build_index([row])).execute(customer_id="C10086")
    assert result["total_value"] == "10000.010000"


@pytest.mark.parametrize("value,currency,unit", [
    ("100美元", "CNY", ""), ("1元", "CNY", "万元"),
    ("1e3", "CNY", ""), ("NaN", "CNY", ""), ("10%", "CNY", ""),
    ("$100", None, ""), ("¥100", None, ""), ("9" * 39, "CNY", ""),
])
def test_ambiguous_or_conflicting_amounts_are_rejected(value, currency, unit):
    with pytest.raises(ValueError):
        parse_money(value, currency, unit)


def test_legacy_english_columns_have_same_semantics(build_index):
    retriever = build_index([{
        "customer_id": "C10086", "product_code": "001234", "holding_value": "0.25", "currency": "CNY",
    }])
    assert CustomerHoldingTool(retriever).execute(customer_id="C10086")["total_value"] == "0.25"


def test_conflicting_aliases_fail_instead_of_omitting_a_record():
    with pytest.raises(ValueError, match="存在冲突"):
        normalize_row({"客户编号": "C1", "customer_id": "C2"})
    assert parse_money("0.1", "CNY")[0] == Decimal("0.1")


def test_empty_selection_is_distinct_from_a_zero_valued_holding(build_index):
    tool = CustomerHoldingTool(build_index([holding(持仓市值="0.00")]))
    zero = tool.execute(customer_id="C10086")
    empty = tool.execute(customer_id="MISSING")
    assert zero["total_value"] == "0.00"
    assert empty["count"] == 0
    assert empty["total_value"] is None
    assert empty["total_value_by_currency"] == {}


def test_rebuilding_index_replaces_structured_rows(build_index):
    retriever = build_index([holding()])
    retriever.build_index_from_parsed([ParsedDocument("new.pdf", 1, [ParsedTable(1, 0, [], [contract("NEW")])])])
    assert CustomerHoldingTool(retriever).execute(customer_id="C10086")["count"] == 0
    assert ContractQueryTool(retriever).execute(contract_id="NEW")["count"] == 1


def test_real_business_http_routes_work_without_a_model_and_are_authenticated(build_index):
    import src.main as main

    retriever = build_index([contract(), holding(持仓市值="1,000.10")])
    # Do not enter TestClient's lifespan: it would warm up a real LLM service.
    client = TestClient(main.app)
    with patch.object(main, "retriever", retriever), patch.object(main.settings, "env", "production"), patch.object(main.settings, "api_key", "k" * 32):
        assert client.post("/api/holdings/query", json={"customer_id": "C10086"}).status_code == 401
        headers = {"Authorization": "Bearer " + "k" * 32}
        response = client.post("/api/holdings/query", json={"customer_id": "C10086"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["total_value"] == "1000.10"
        assert response.json()["results"][0]["metadata"]["source"] == "fictional_business.pdf"
        response = client.post("/api/contracts/query", json={"min_amount": "1000.10", "currency": "CNY"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert client.post("/api/contracts/query", json={"min_amount": "1000"}, headers=headers).status_code == 422
    client.close()


def test_business_http_routes_explain_missing_index():
    import src.main as main

    client = TestClient(main.app)
    with patch.object(main, "retriever", None), patch.object(main.settings, "api_key", ""), patch.object(main.settings, "env", "development"):
        response = client.post("/api/holdings/query", json={"customer_id": "C10086"})
    client.close()
    assert response.status_code == 503
    assert response.json()["detail"] == "请先构建文档索引"


@pytest.mark.asyncio
async def test_agent_fallback_preserves_total_limit_and_source_evidence(build_index):
    from src.agents.financial_agent import FinancialAgentGraph

    retriever = build_index([holding(f"{i:06}") for i in range(25)])
    llm = MagicMock()
    llm.chat_completions_create = AsyncMock(side_effect=[
        {"choices": [{"message": {"content": '{"intent":"customer_holding","confidence":1,"params":{"customer_id":"C10086"}}'}}]},
        RuntimeError("offline formatting service"),
    ])
    result = await FinancialAgentGraph(retriever, llm).run("查询 C10086 的全部持仓")
    assert "CNY）：2.50" in result["final_response"]
    assert "fictional_business.pdf" in result["final_response"]
    assert "共 25 条" in result["final_response"]


@pytest.mark.asyncio
async def test_agent_asks_for_currency_before_executing_an_amount_query(build_index):
    from src.agents.financial_agent import FinancialAgentGraph

    llm = MagicMock()
    llm.chat_completions_create = AsyncMock(return_value={"choices": [{"message": {
        "content": '{"intent":"contract_query","confidence":1,"params":{"min_amount":"1000"}}',
    }}]})
    result = await FinancialAgentGraph(build_index([contract()]), llm).run("找金额超过 1000 的合同")
    assert "必须指定币种" in result["final_response"]
    assert result["tool_result"] is None
    assert llm.chat_completions_create.await_count == 1


def test_offline_index_mode_never_loads_optional_models(monkeypatch):
    retriever = HybridRetriever(enable_optional_models=False)
    monkeypatch.setattr(retriever, "_build_vector_index", MagicMock(side_effect=AssertionError("no vector models")))
    monkeypatch.setattr(retriever, "_load_reranker", MagicMock(side_effect=AssertionError("no reranker")))
    retriever.build_index_from_parsed([ParsedDocument("offline.pdf", 1, [ParsedTable(1, 0, [], [contract()])])])
    assert ContractQueryTool(retriever).execute(contract_id="HT001")["count"] == 1
