"""确定性合成数据生成器（无需任何外部数据源即可运行）

说明：
- 行情使用固定随机种子，保证每次运行结果一致、可复现；
- 行情在「市场因子 + 个股 Beta + 特质波动」结构下生成，Beta 才有真实经济含义；
- 财报为结构化三大表，含逐年成长与噪声，用于演示比率 / 同比 / 异常预警。

真实部署时，可将 load_* 替换为 westock-data / 数据仓库的取数实现。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 20240817
START_DATE = "2023-01-02"
END_DATE = "2025-12-31"
TRADING_DAYS = 252

# 5 只标的，覆盖不同 Beta / 波动率 / 动量特征
UNIVERSE: dict[str, dict] = {
    "688001.SH": {"name": "星辰科技", "beta": 1.35, "idio_vol": 0.018, "base": 42.0, "mom": 0.55},
    "600519.SH": {"name": "黔风白酒", "beta": 0.85, "idio_vol": 0.014, "base": 1680.0, "mom": 0.30},
    "300750.SZ": {"name": "远创新能", "beta": 1.20, "idio_vol": 0.022, "base": 188.0, "mom": 0.10},
    "601318.SH": {"name": "平安保融", "beta": 0.70, "idio_vol": 0.012, "base": 48.0, "mom": -0.05},
    "000858.SZ": {"name": "五粮醇香", "beta": 0.95, "idio_vol": 0.016, "base": 155.0, "mom": 0.18},
}

# 有完整财报的标的（其余仅给行情）
FINANCIAL_UNIVERSE = ["688001.SH", "600519.SH", "300750.SZ"]


def _trading_days(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=start, end=end)


# 全局交易日与共享市场因子序列：基准指数与个股生成必须复用同一市场收益，
# 否则 CAPM Beta 估计会因基准不匹配而趋近于 0。
_DAYS = _trading_days(START_DATE, END_DATE)


def _market_returns(n: int, rng: np.random.Generator) -> np.ndarray:
    """市场因子日收益：温和漂移 + 时变波动率（波动率聚集）+ 正态噪声。"""
    drift = 0.0004
    vol = np.empty(n)
    vol[0] = 0.010
    for t in range(1, n):
        # GARCH(1,1)-like 波动率聚集
        vol[t] = np.sqrt(0.0000015 + 0.08 * (vol[t - 1] ** 2) + rng.normal(0, 1) ** 2 * 0.000004)
    shocks = rng.normal(0, 1, n) * vol
    return drift + shocks


def _market_ret_array() -> np.ndarray:
    """共享市场因子日收益序列（固定种子，全局唯一）。"""
    rng = np.random.default_rng(SEED)
    return _market_returns(len(_DAYS), rng)


def load_market_data() -> pd.DataFrame:
    """返回基准指数（收盘）日频序列。"""
    mret = _market_ret_array()
    close = 3000.0 * np.cumprod(1 + mret)
    return pd.DataFrame({"date": _DAYS.strftime("%Y-%m-%d"), "close": np.round(close, 2)})


def load_stock_prices() -> dict[str, pd.DataFrame]:
    """返回每个标的的 OHLC 日频序列（含 open 以支持 next-day-open 撮合）。"""
    rng = np.random.default_rng(SEED + 1)
    days = _DAYS
    n = len(days)
    mret = _market_ret_array()  # 与基准指数同一市场因子

    out: dict[str, pd.DataFrame] = {}
    for code, meta in UNIVERSE.items():
        # 个股收益 = beta * 市场收益 + 特质噪声 + 慢变动量漂移
        mom_drift = meta["mom"] / TRADING_DAYS
        idio = rng.normal(0, 1, n) * meta["idio_vol"]
        ret = meta["beta"] * mret + idio + mom_drift
        close = meta["base"] * np.cumprod(1 + ret)
        # 由收盘反推 open/high/low（仅在 [t-1, t] 区间内，避免前视）
        prev_close = np.concatenate([[meta["base"]], close[:-1]])
        op = prev_close * (1 + rng.normal(0, 0.003, n))
        intraday = np.abs(rng.normal(0, 1, n)) * meta["idio_vol"] * 1.2
        hi = np.maximum(op, close) * (1 + intraday)
        lo = np.minimum(op, close) * (1 - intraday)
        out[code] = pd.DataFrame(
            {
                "date": days.strftime("%Y-%m-%d"),
                "open": np.round(op, 2),
                "high": np.round(hi, 2),
                "low": np.round(lo, 2),
                "close": np.round(close, 2),
            }
        )
    return out


def load_financials() -> dict[str, dict]:
    """返回结构化三大表（年度）。真实部署可替换为财报接口。"""
    rng = np.random.default_rng(SEED + 7)
    years = [2022, 2023, 2024, 2025]

    # 每个标的的初始规模与成长率
    profile = {
        "688001.SH": {"rev0": 12.0, "growth": 0.28, "margin": 0.42, "asset0": 20.0},
        "600519.SH": {"rev0": 110.0, "growth": 0.16, "margin": 0.52, "asset0": 240.0},
        "300750.SZ": {"rev0": 38.0, "growth": 0.22, "margin": 0.18, "asset0": 70.0},
    }

    result: dict[str, dict] = {}
    for code, p in profile.items():
        income, balance, cashflow = [], [], []
        rev = p["rev0"]
        for i, y in enumerate(years):
            g = p["growth"] * (1 + rng.normal(0, 0.15))
            if i > 0:
                rev = rev * (1 + g)
            revenue = rev * (1 + rng.normal(0, 0.02))
            cogs = revenue * (1 - p["margin"] + rng.normal(0, 0.01))
            gross_profit = revenue - cogs
            opex = revenue * (0.18 + rng.normal(0, 0.01))
            op_profit = gross_profit - opex
            fin_exp = revenue * 0.02
            pretax = op_profit - fin_exp
            tax = pretax * 0.15
            net_profit = pretax - tax

            total_assets = p["asset0"] * (1 + 0.20 * i) * (1 + rng.normal(0, 0.03))
            total_liab = total_assets * (0.38 + 0.04 * i + rng.normal(0, 0.02))
            equity = total_assets - total_liab
            current_assets = total_assets * (0.45 + rng.normal(0, 0.02))
            current_liab = total_liab * (0.7 + rng.normal(0, 0.02))
            ar = revenue * (0.18 + rng.normal(0, 0.01))  # 应收账款
            inventory = revenue * (0.12 + rng.normal(0, 0.01))

            cfo = net_profit * (1.1 + rng.normal(0, 0.05))  # 经营现金流
            capex = revenue * (0.10 + rng.normal(0, 0.01))
            fcf = cfo - capex

            income.append(
                {
                    "year": y,
                    "revenue": round(revenue, 2),
                    "cogs": round(cogs, 2),
                    "gross_profit": round(gross_profit, 2),
                    "opex": round(opex, 2),
                    "operating_profit": round(op_profit, 2),
                    "financial_expense": round(fin_exp, 2),
                    "pretax_profit": round(pretax, 2),
                    "net_profit": round(net_profit, 2),
                }
            )
            balance.append(
                {
                    "year": y,
                    "total_assets": round(total_assets, 2),
                    "total_liabilities": round(total_liab, 2),
                    "equity": round(equity, 2),
                    "current_assets": round(current_assets, 2),
                    "current_liabilities": round(current_liab, 2),
                    "accounts_receivable": round(ar, 2),
                    "inventory": round(inventory, 2),
                }
            )
            cashflow.append(
                {
                    "year": y,
                    "operating_cash_flow": round(cfo, 2),
                    "capex": round(capex, 2),
                    "free_cash_flow": round(fcf, 2),
                }
            )

        result[code] = {
            "name": UNIVERSE[code]["name"],
            "years": years,
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cashflow,
        }
    return result
