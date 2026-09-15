"""动量因子策略回测（A 股多空合规）

严格遵循回测明算专家口径：
- 信号在第 i 日基于已收盘数据生成，第 i+1 日开盘撮合（杜绝前视）；
- 指标使用 warmup 段加载，仅在评估窗内产生交易与净值；
- A 股：100 股整手、T+1、多空仅做多；
- 费用：买入佣金 3bps、卖出佣金 3bps + 印花税 0.05%；
- 期末强制平仓并确认空仓后导出。

产出：<prefix>_equity.csv / <prefix>_trades.csv / <prefix>_summary.json + index.html 仪表盘。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许从仓库根目录以脚本方式运行。
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.factors.dashboard.export_results import export_results
from src.factors.dashboard.render_dashboard import (
    build_dashboard_data,
    render_dashboard,
)
from src.factors.demo_data import load_stock_prices

WARMUP = 120  # 指标预热天数
FAST = 20
SLOW = 60
BUY_COMM = 0.0003
SELL_COMM = 0.0003
STAMP = 0.0005
LOT = 100
INIT_CASH = 1_000_000.0
MARKET = "china_a"


def roc(close, w: int) -> float:
    if len(close) <= w:
        return 0.0
    return close.iloc[-1] / close.iloc[-1 - w] - 1.0


def run(code: str, out_dir: str | Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prices = load_stock_prices()[code]
    df = prices.copy()
    df["date"] = df["date"].astype(str)

    # 加载起始 = 评估起始 - warmup 余量
    eval_start_idx = WARMUP
    # 评估窗起始日期
    start_date = df["date"].iloc[eval_start_idx]
    end_date = df["date"].iloc[-1]

    cash = INIT_CASH
    position = 0
    pending_buy = False
    pending_sell = False
    equity_curve: list[dict] = []
    trade_history: list[dict] = []
    entry: dict | None = None

    for i in range(len(df)):
        row = df.iloc[i]
        date = row["date"]
        op = float(row["open"])
        cl = float(row["close"])

        # 1) 先执行上一根 bar 的挂单（次日均价撮合）
        if pending_buy and position == 0:
            size = int((cash * 0.95) / (op * LOT)) * LOT
            if size > 0:
                cost = size * op * (1 + BUY_COMM)
                if cost <= cash:
                    cash -= cost
                    position = size
                    entry = {"entry_date": date, "entry_price": op, "size": size}
            pending_buy = False
        if pending_sell and position > 0:
            proceeds = position * op * (1 - SELL_COMM - STAMP)
            cash += proceeds
            pnl = proceeds - entry["size"] * entry["entry_price"] * (1 + BUY_COMM)
            pnl_pct = (op / entry["entry_price"] - 1) * 100 - (BUY_COMM + SELL_COMM + STAMP) * 100
            trade_history.append(
                {
                    "entry_date": entry["entry_date"],
                    "exit_date": date,
                    "side": "long",
                    "size": entry["size"],
                    "entry_price": entry["entry_price"],
                    "exit_price": op,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 3),
                    "holding_bars": i - df.index[df["date"] == entry["entry_date"]][0],
                    "symbol": code,
                    "symbol_name": code,
                }
            )
            position = 0
            entry = None
            pending_sell = False

        # 2) 生成今日信号（用截至今日的收盘，明日开盘执行）
        if i >= SLOW:
            fast_roc = roc(df["close"].iloc[: i + 1], FAST)
            slow_roc = roc(df["close"].iloc[: i + 1], SLOW)
            if position == 0 and fast_roc > slow_roc and fast_roc > 0:
                pending_buy = True
            elif position > 0 and fast_roc < slow_roc:
                pending_sell = True

        # 3) 记录净值（仅评估窗内）
        equity = cash + position * cl
        if i >= eval_start_idx:
            equity_curve.append({"date": date, "value": round(equity, 2)})

    # 期末强制平仓
    if position > 0:
        last = df.iloc[-1]
        op = float(last["open"])
        proceeds = position * op * (1 - SELL_COMM - STAMP)
        cash += proceeds
        pnl = proceeds - entry["size"] * entry["entry_price"] * (1 + BUY_COMM)
        pnl_pct = (op / entry["entry_price"] - 1) * 100 - (BUY_COMM + SELL_COMM + STAMP) * 100
        trade_history.append(
            {
                "entry_date": entry["entry_date"],
                "exit_date": last["date"],
                "side": "long",
                "size": entry["size"],
                "entry_price": entry["entry_price"],
                "exit_price": op,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 3),
                "holding_bars": len(df) - 1 - df.index[df["date"] == entry["entry_date"]][0],
                "symbol": code,
                "symbol_name": code,
            }
        )
        position = 0

    prefix = f"momentum_{code.replace('.', '')}"
    # 对齐 export_results 列名 holding_bars -> int
    for t in trade_history:
        t["holding_bars"] = int(t["holding_bars"])

    paths = export_results(
        equity_curve=equity_curve,
        trade_history=trade_history,
        prefix=prefix,
        initial_cash=INIT_CASH,
        start=start_date,
        end=end_date,
        market=MARKET,
        output_dir=out_dir,
        strategy_name=f"动量因子(ROC{FAST}/{SLOW}) {code}",
        symbol=code,
        is_flat_at_end=True,
    )

    # 渲染专家仪表盘
    report_data = build_dashboard_data(
        equity_csv=str(paths["equity"]),
        trades_csv=str(paths["trades"]),
        summary_json=str(paths["summary"]),
        language="zh",
        market=MARKET,
        extra_modules=[
            {
                "type": "text",
                "tab": "overview",
                "title": "关键结论",
                "text": "动量因子在评估窗内以次日均价撮合，多空仅做多；"
                "期末强制平仓。该结果由 AI 基于合成数据回测生成，仅作方法演示，不构成投资建议。",
            }
        ],
    )
    dashboard_path = out_dir / "index.html"
    render_dashboard(report_data, output_path=dashboard_path)

    return {
        "files": {k: str(v) for k, v in paths.items()},
        "dashboard": str(dashboard_path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="688001.SH")
    ap.add_argument("--out", default=str(ROOT / "data" / "backtest"))
    args = ap.parse_args()
    result = run(args.code, args.out)
    print("回测产物：")
    for k, v in result["files"].items():
        print(f"  {k}: {v}")
    print(f"  仪表盘: {result['dashboard']}")


if __name__ == "__main__":
    main()
