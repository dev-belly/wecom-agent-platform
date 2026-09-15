"""量化因子与财报分析模块

包含：
- demo_data:        确定性合成行情 / 财报数据（无外部依赖可运行）
- risk_factors:     风险因子 + 风格因子引擎（向量化、无前视偏差）
- financial_report: 财报三大表解析 / 财务比率 / 同比趋势 / 异常预警
- factor_backtest:  动量因子策略回测（A 股多空合规，产出标准三件套 + 仪表盘）
"""

from .demo_data import load_financials, load_market_data, load_stock_prices
from .financial_report import FinancialReportAnalyzer
from .risk_factors import FactorEngine

__all__ = [
    "load_market_data",
    "load_stock_prices",
    "load_financials",
    "FactorEngine",
    "FinancialReportAnalyzer",
]
