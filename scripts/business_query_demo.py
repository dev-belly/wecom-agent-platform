"""Run the fictional contract/holding workflow offline, without any model."""

import json
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parsers.pdf_parser import ParsedDocument
from src.retrieval.hybrid_retriever import HybridRetriever
from src.tools.business_tools import ContractQueryTool, CustomerHoldingTool


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    logger.disable("src.retrieval.hybrid_retriever")
    document = ParsedDocument.from_dict(json.loads(
        (ROOT / "data/business-demo/parsed.json").read_text(encoding="utf-8"),
    ))
    retriever = HybridRetriever(enable_optional_models=False)
    retriever.build_index_from_parsed([document])
    contracts = ContractQueryTool(retriever)
    holdings = CustomerHoldingTool(retriever)
    scenarios = {
        "exact_contract_id": contracts.execute(contract_id="HT001"),
        "cny_contracts_signed_in_2024": contracts.execute(
            date_range_start="2024-01-01", date_range_end="2024-12-31",
            min_amount="1000.10", currency="CNY",
        ),
        "complete_holding_total": holdings.execute(customer_id="C10086"),
        "incomplete_valuation": holdings.execute(customer_id="C20000"),
    }
    assert scenarios["exact_contract_id"]["count"] == 1
    assert scenarios["cny_contracts_signed_in_2024"]["count"] == 1
    assert scenarios["complete_holding_total"]["total_value"] == "1000.30"
    assert scenarios["incomplete_valuation"]["total_value"] is None
    print(json.dumps({
        "provenance": document.metadata["provenance"], "scenarios": scenarios,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
