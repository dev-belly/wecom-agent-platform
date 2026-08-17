"""计算量化 Demo 所需的真实数值，输出 JSON 供前端 mock 使用。"""
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from factors.demo_data import load_market_data, load_stock_prices, load_financials  # noqa: E402
from factors.risk_factors import FactorEngine  # noqa: E402
from factors.financial_report import FinancialReportAnalyzer  # noqa: E402

engine = FactorEngine()
market = load_market_data()
mclose = market.set_index("date")["close"]
prices = load_stock_prices()
financials = load_financials()

# 每标的风险 + 风格因子
per_stock = {}
for code, df in prices.items():
    close = df.set_index("date")["close"]
    risk = engine.compute_risk_metrics(close, mclose)
    style = engine.compute_style_factors(close)
    per_stock[code] = {
        "name": financials.get(code, {}).get("name", code),
        "price": round(float(close.iloc[-1]), 2),
        "risk": risk,
        "style": style,
    }

# 排行榜
leaderboard = engine.cross_sectional_leaderboard(prices, financials, mclose)

# 财报
analyzer = FinancialReportAnalyzer(financials)
reports = {code: analyzer.summarize(code) for code in financials}

# 回测 summary
bt_path = Path(__file__).resolve().parents[1] / "data" / "backtest" / "momentum_688001SH_summary.json"
bt = json.loads(bt_path.read_text(encoding="utf-8")) if bt_path.exists() else {}

out = {
    "per_stock": per_stock,
    "leaderboard": leaderboard,
    "reports": reports,
    "backtest": bt,
    "market_name": "沪深300(合成基准)",
}
print(json.dumps(out, ensure_ascii=False, indent=2))
