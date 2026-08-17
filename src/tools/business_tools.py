"""业务工具集 — 8 类金融查询工具"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator
from loguru import logger

from retrieval.hybrid_retriever import HybridRetriever


# ── 工具参数模型（自动校验）─

class ContractQueryParams(BaseModel):
    """合同查询参数"""
    contract_id: Optional[str] = Field(None, description="合同编号")
    party_a: Optional[str] = Field(None, description="甲方名称")
    party_b: Optional[str] = Field(None, description="乙方名称")
    date_range_start: Optional[date] = Field(None, description="签约日期起始")
    date_range_end: Optional[date] = Field(None, description="签约日期截止")
    min_amount: Optional[float] = Field(None, gt=0, description="最小金额")


class ProductNavQueryParams(BaseModel):
    """产品净值查询参数"""
    product_code: Optional[str] = Field(None, description="产品代码")
    product_name: Optional[str] = Field(None, description="产品名称（模糊匹配）")
    nav_date: Optional[date] = Field(None, description="净值日期")


class CustomerHoldingParams(BaseModel):
    """客户持仓查询参数"""
    customer_id: Optional[str] = Field(None, description="客户编号")
    customer_name: Optional[str] = Field(None, description="客户姓名")
    product_code: Optional[str] = Field(None, description="产品代码（筛选）")


class RiskAssessmentParams(BaseModel):
    """风险评估参数"""
    customer_id: str = Field(..., description="客户编号")
    assessment_type: str = Field("suitability", description="评估类型: suitability/exposure/concentration")


class RiskFactorQueryParams(BaseModel):
    """风险因子查询参数"""
    code: Optional[str] = Field(None, description="标的代码，如 688001.SH；不填则返回全市场概览")
    metric: Optional[str] = Field(None, description="指定因子: sharpe/beta/max_drawdown/var 等")


class FinancialReportQueryParams(BaseModel):
    """财报分析查询参数"""
    code: Optional[str] = Field(None, description="标的代码，如 300750.SZ")


class FactorMiningParams(BaseModel):
    """因子挖掘/排行榜参数"""
    top_n: Optional[int] = Field(None, gt=0, description="返回前 N 名，默认全部")


# ── 工具基类 ──────────────────────────────────────────

class BaseTool:
    """所有业务工具的基类"""

    name: str = ""
    description: str = ""
    parameters_schema: dict = {}

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever

    def execute(self, **kwargs) -> dict:
        raise NotImplementedError

    def _search(self, query: str, top_k: int = 5) -> list[dict]:
        """统一调用混合检索"""
        return self.retriever.retrieve(query, top_k=top_k)


# ── 8 类业务工具实现 ──────────────────────────────────

class ContractQueryTool(BaseTool):
    """工具 1: 合同信息查询"""

    name = "contract_query"
    description = "查询金融合同信息，支持按合同编号、甲方、乙方、金额范围、签约日期等条件筛选"
    parameters_schema = ContractQueryParams.model_json_schema()

    def execute(self, **kwargs) -> dict:
        params = ContractQueryParams(**kwargs)
        conditions = []
        if params.contract_id:
            conditions.append(params.contract_id)
        if params.party_a:
            conditions.append(f"甲方:{params.party_a}")
        if params.party_b:
            conditions.append(f"乙方:{params.party_b}")
        if params.min_amount:
            conditions.append(f"金额>={params.min_amount}")

        query = " ".join(conditions) if conditions else "合同信息"
        results = self._search(query, top_k=10)

        # 后过滤
        filtered = []
        for r in results:
            row = self._parse_result_row(r["text"])
            if params.date_range_start and row.get("sign_date"):
                sd = self._parse_date(row["sign_date"])
                if sd and sd < params.date_range_start:
                    continue
            if params.date_range_end and row.get("sign_date"):
                ed = self._parse_date(row["sign_date"])
                if ed and ed > params.date_range_end:
                    continue
            filtered.append({**r, "parsed": row})

        return {
            "tool": self.name,
            "params": kwargs,
            "count": len(filtered),
            "results": filtered[:10],
        }


class ProductNavTool(BaseTool):
    """工具 2: 产品净值查询"""

    name = "product_nav"
    description = "查询金融产品净值信息，包括单位净值、累计净值、日增长率等"
    parameters_schema = ProductNavQueryParams.model_json_schema()

    def execute(self, **kwargs) -> dict:
        params = ProductNavQueryParams(**kwargs)
        parts = ["产品", "净值"]
        if params.product_code:
            parts.append(params.product_code)
        if params.product_name:
            parts.append(params.product_name)
        if params.nav_date:
            parts.append(params.nav_date.isoformat())

        query = " ".join(parts)
        results = self._search(query, top_k=10)

        parsed_results = []
        for r in results:
            row = self._parse_result_row(r["text"])
            parsed_results.append({**r, "parsed": row})

        return {
            "tool": self.name,
            "params": kwargs,
            "count": len(parsed_results),
            "results": parsed_results[:10],
        }


class CustomerHoldingTool(BaseTool):
    """工具 3: 客户持仓查询"""

    name = "customer_holding"
    description = "查询客户持仓信息，包括持仓份额、持仓市值等"
    parameters_schema = CustomerHoldingParams.model_json_schema()

    def execute(self, **kwargs) -> dict:
        params = CustomerHoldingParams(**kwargs)
        parts = ["客户", "持仓"]
        if params.customer_id:
            parts.append(params.customer_id)
        if params.customer_name:
            parts.append(params.customer_name)
        if params.product_code:
            parts.append(params.product_code)

        query = " ".join(parts)
        results = self._search(query, top_k=10)

        parsed_results = []
        for r in results:
            row = self._parse_result_row(r["text"])
            parsed_results.append({**r, "parsed": row})

        # 汇总
        total_value = sum(
            (p.get("parsed", {}).get("holding_value") or 0)
            for p in parsed_results
            if isinstance(p.get("parsed", {}).get("holding_value"), (int, float))
        )

        return {
            "tool": self.name,
            "params": kwargs,
            "count": len(parsed_results),
            "total_value": total_value,
            "results": parsed_results[:20],
        }


class ProductInfoTool(BaseTool):
    """工具 4: 产品基本信息查询"""

    name = "product_info"
    description = "查询金融产品基本信息：产品代码、名称、类型、风险等级、费率、管理人、托管行等"

    def execute(self, **kwargs) -> dict:
        product_code = kwargs.get("product_code") or kwargs.get("product_name", "")
        query = f"产品 信息 {product_code}"
        results = self._search(query, top_k=5)

        return {
            "tool": self.name,
            "params": kwargs,
            "results": [
                {**r, "parsed": self._parse_result_row(r["text"])}
                for r in results
            ],
        }


class FeeQueryTool(BaseTool):
    """工具 5: 费率查询"""

    name = "fee_query"
    description = "查询各类产品的费率信息，包括管理费、托管费、申购赎回费等"

    def execute(self, **kwargs) -> dict:
        product_code = kwargs.get("product_code", "")
        query = f"费率 {product_code}" if product_code else "费率"
        results = self._search(query, top_k=5)

        return {
            "tool": self.name,
            "params": kwargs,
            "results": [
                {**r, "parsed": self._parse_result_row(r["text"])}
                for r in results
            ],
        }


class RiskQueryTool(BaseTool):
    """工具 6: 风险等级查询"""

    name = "risk_query"
    description = "查询产品或客户的风险等级、风险评估信息"

    def execute(self, **kwargs) -> dict:
        target = kwargs.get("target", "")  # 产品代码或客户ID
        query = f"风险等级 {target}"
        results = self._search(query, top_k=5)

        return {
            "tool": self.name,
            "params": kwargs,
            "results": [
                {**r, "parsed": self._parse_result_row(r["text"])}
                for r in results
            ],
        }


class CustodyBankTool(BaseTool):
    """工具 7: 托管银行信息查询"""

    name = "custody_bank"
    description = "查询产品的托管银行、账户信息等"

    def execute(self, **kwargs) -> dict:
        product_code = kwargs.get("product_code", "")
        query = f"托管银行 {product_code}" if product_code else "托管银行"
        results = self._search(query, top_k=5)

        return {
            "tool": self.name,
            "params": kwargs,
            "results": [
                {**r, "parsed": self._parse_result_row(r["text"])}
                for r in results
            ],
        }


class FundManagerTool(BaseTool):
    """工具 8: 基金管理人信息查询"""

    name = "fund_manager"
    description = "查询基金管理人/产品管理人相关信息"

    def execute(self, **kwargs) -> dict:
        manager_name = kwargs.get("manager_name", "")
        query = f"基金管理人 {manager_name}" if manager_name else "基金管理人"
        results = self._search(query, top_k=5)

        return {
            "tool": self.name,
            "params": kwargs,
            "results": [
                {**r, "parsed": self._parse_result_row(r["text"])}
                for r in results
            ],
        }


# ── 量化因子类工具（9 / 10 / 11）─────────────────────

class RiskFactorQueryTool(BaseTool):
    """工具 9: 风险因子查询"""

    name = "risk_factor_query"
    description = "计算标的的风险因子：年化收益/波动、Sharpe、Sortino、最大回撤、Calmar、Beta、Alpha、VaR/CVaR"

    def execute(self, **kwargs) -> dict:
        from factors.demo_data import load_market_data, load_stock_prices
        from factors.risk_factors import FactorEngine

        params = RiskFactorQueryParams(**kwargs)
        engine = FactorEngine()
        mclose = load_market_data().set_index("date")["close"]
        prices = load_stock_prices()

        if params.code:
            if params.code not in prices:
                return {"tool": self.name, "error": f"未找到标的 {params.code}"}
            df = prices[params.code].set_index("date")["close"]
            risk = engine.compute_risk_metrics(df, mclose)
            style = engine.compute_style_factors(df)
            return {
                "tool": self.name,
                "params": kwargs,
                "code": params.code,
                "risk": risk,
                "style": style,
            }

        # 全市场概览
        overview = []
        for code, df in prices.items():
            close = df.set_index("date")["close"]
            r = engine.compute_risk_metrics(close, mclose)
            overview.append({"code": code, "sharpe": r["sharpe"], "beta": r["beta"],
                             "max_drawdown": r["max_drawdown"], "annual_return": r["annual_return"]})
        overview.sort(key=lambda x: x["sharpe"], reverse=True)
        return {"tool": self.name, "params": kwargs, "overview": overview}


class FinancialReportQueryTool(BaseTool):
    """工具 10: 财报分析"""

    name = "financial_report_query"
    description = "解析财报三大表，输出财务比率（ROE/毛利率/资产负债率等）、同比趋势与异常预警"

    def execute(self, **kwargs) -> dict:
        from factors.demo_data import load_financials
        from factors.financial_report import FinancialReportAnalyzer

        params = FinancialReportQueryParams(**kwargs)
        financials = load_financials()
        analyzer = FinancialReportAnalyzer(financials)

        if params.code:
            if params.code not in financials:
                return {"tool": self.name, "error": f"未找到 {params.code} 的财报数据"}
            return {"tool": self.name, "params": kwargs, "report": analyzer.summarize(params.code)}

        return {"tool": self.name, "params": kwargs, "reports": [analyzer.summarize(c) for c in financials]}


class FactorMiningTool(BaseTool):
    """工具 11: 因子挖掘 / 多因子排行榜"""

    name = "factor_mining"
    description = "对股票池做多因子暴露计算（动量/价值/质量/成长/低波），截面 z-score 合成综合因子得分排行"

    def execute(self, **kwargs) -> dict:
        from factors.demo_data import load_market_data, load_stock_prices, load_financials
        from factors.risk_factors import FactorEngine

        params = FactorMiningParams(**kwargs)
        engine = FactorEngine()
        mclose = load_market_data().set_index("date")["close"]
        prices = load_stock_prices()
        financials = load_financials()

        rows = engine.cross_sectional_leaderboard(prices, financials, mclose)
        if params.top_n:
            rows = rows[: params.top_n]
        return {"tool": self.name, "params": kwargs, "count": len(rows), "leaderboard": rows}


# ── 工具注册表 ───────────────────────────────────────

TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    "contract_query": ContractQueryTool,
    "product_nav": ProductNavTool,
    "customer_holding": CustomerHoldingTool,
    "product_info": ProductInfoTool,
    "fee_query": FeeQueryTool,
    "risk_query": RiskQueryTool,
    "custody_bank": CustodyBankTool,
    "fund_manager": FundManagerTool,
    "risk_factor_query": RiskFactorQueryTool,
    "financial_report_query": FinancialReportQueryTool,
    "factor_mining": FactorMiningTool,
}


def get_all_tools(retriever: HybridRetriever) -> list[BaseTool]:
    """获取所有工具实例"""
    return [cls(retriever) for cls in TOOL_REGISTRY.values()]


def get_tool(name: str, retriever: HybridRetriever) -> BaseTool:
    """按名称获取工具实例"""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"未知工具: {name}，可用工具: {list(TOOL_REGISTRY.keys())}")
    return TOOL_REGISTRY[name](retriever)


# ── 通用辅助方法 ──────────────────────────────────────

@staticmethod
def _parse_result_row(text: str) -> dict:
    """将检索结果文本行解析为字典"""
    row = {}
    for segment in text.split(" | "):
        if ":" in segment:
            key, _, val = segment.partition(":")
            row[key.strip()] = val.strip()
    return row


@staticmethod
def _parse_date(date_str: str) -> Optional[date]:
    """解析多种日期格式"""
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y-%m-%d %H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# 将静态方法挂到基类上
BaseTool._parse_result_row = _parse_result_row.__func__
BaseTool._parse_date = _parse_date.__func__
