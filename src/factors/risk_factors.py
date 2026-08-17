"""风险因子与风格因子引擎

设计原则（与回测明算专家的防前视口径一致）：
- 全部使用 pandas / numpy 向量化计算，避免手写循环；
- 任何「用第 i 日信息生成信号、在第 i+1 日开盘执行」的语义都在调用方保证，
  本模块只做无状态的截面 / 时序统计；
- Beta / Alpha 基于 CAPM，使用同期市场收益，不引入未来信息。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().fillna(0.0)


def _max_drawdown(cum: np.ndarray) -> float:
    peak = np.maximum.accumulate(cum)
    dd = cum / peak - 1.0
    return float(dd.min())


class FactorEngine:
    """风险因子 + 风格因子计算。"""

    # ── 单一标的的风险指标 ─────────────────────────────
    def compute_risk_metrics(
        self,
        stock_close: pd.Series,
        market_close: pd.Series | None = None,
        risk_free_annual: float = 0.0,
    ) -> dict:
        """计算个股风险指标。

        Args:
            stock_close: 个股收盘价序列（按日期升序）
            market_close: 基准收盘价序列（同长度，与个股同期）
            risk_free_annual: 无风险年化收益率（默认 0）
        """
        ret = daily_returns(stock_close).iloc[1:]
        n = len(ret)
        if n < 2:
            return {}

        rf_daily = risk_free_annual / TRADING_DAYS
        mean_d = float(ret.mean())
        std_d = float(ret.std(ddof=1))

        ann_return = float((1 + ret).prod() ** (TRADING_DAYS / n) - 1.0)
        ann_vol = std_d * np.sqrt(TRADING_DAYS)
        sharpe = (mean_d - rf_daily) / std_d * np.sqrt(TRADING_DAYS) if std_d > 0 else 0.0

        # Sortino：仅用下行波动
        downside = ret[ret < rf_daily] - rf_daily
        dd_dev = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
        sortino = (mean_d - rf_daily) / dd_dev * np.sqrt(TRADING_DAYS) if dd_dev > 0 else 0.0

        cum = (1 + ret).cumprod().values
        mdd = _max_drawdown(cum)
        calmar = ann_return / abs(mdd) if mdd < 0 else 0.0

        # 历史 VaR / CVaR（日频），并给出年化近似
        var_95 = float(np.percentile(ret, 5))
        var_99 = float(np.percentile(ret, 1))
        tail = ret[ret <= var_95]
        cvar_95 = float(tail.mean()) if len(tail) else var_95

        # CAPM：Beta / Alpha
        beta = 0.0
        alpha = ann_return
        if market_close is not None:
            mret = daily_returns(market_close).iloc[1:].reset_index(drop=True)
            sret = ret.reset_index(drop=True)
            mret = mret.iloc[: len(sret)]
            cov = np.cov(sret, mret)
            if cov.shape == (2, 2) and cov[1, 1] > 0:
                beta = float(cov[0, 1] / cov[1, 1])
                ann_mkt = float((1 + mret).prod() ** (TRADING_DAYS / len(mret)) - 1.0)
                alpha = ann_return - (risk_free_annual + beta * (ann_mkt - risk_free_annual))

        skew = float(ret.skew())
        kurt = float(ret.kurt())

        return {
            "annual_return": round(ann_return, 4),
            "annual_vol": round(ann_vol, 4),
            "sharpe": round(float(sharpe), 3),
            "sortino": round(float(sortino), 3),
            "max_drawdown": round(mdd, 4),
            "calmar": round(float(calmar), 3),
            "beta": round(beta, 3),
            "alpha": round(float(alpha), 4),
            "var_95_daily": round(var_95, 5),
            "var_99_daily": round(var_99, 5),
            "cvar_95_daily": round(cvar_95, 5),
            "var_95_annual": round(var_95 * np.sqrt(TRADING_DAYS), 4),
            "cvar_95_annual": round(cvar_95 * np.sqrt(TRADING_DAYS), 4),
            "skew": round(skew, 3),
            "kurtosis": round(kurt, 3),
        }

    # ── 风格因子（price-based）─────────────────────────
    def compute_style_factors(self, stock_close: pd.Series) -> dict:
        close = stock_close.astype(float)
        mom = {}
        for w in (20, 60, 120):
            if len(close) > w:
                mom[f"momentum_{w}"] = round(float(close.iloc[-1] / close.iloc[-1 - w] - 1.0), 4)
            else:
                mom[f"momentum_{w}"] = 0.0
        ret = daily_returns(close).iloc[1:]
        vol_annual = float(ret.std(ddof=1) * np.sqrt(TRADING_DAYS))
        return {
            **mom,
            "volatility_annual": round(vol_annual, 4),
            "recent_20d_return": mom["momentum_20"],
        }

    # ── 跨标的因子排行榜（截面 z-score）─────────────────
    def cross_sectional_leaderboard(
        self,
        stock_prices: dict[str, pd.DataFrame],
        financials: dict[str, dict] | None = None,
        market_close: pd.Series | None = None,
    ) -> list[dict]:
        """计算每只标的的多因子暴露，截面 z-score 标准化后合成综合因子得分。

        因子：动量(Momentum)、低波(LowVol)、质量(Quality=ROE)、
              成长(Growth=营收CAGR)、价值(Value=经营利润率/总资产)。
        """
        rows: list[dict] = []
        for code, df in stock_prices.items():
            close = df["close"]
            risk = self.compute_risk_metrics(close, market_close) if market_close is not None else self.compute_risk_metrics(close)
            style = self.compute_style_factors(close)
            row = {
                "code": code,
                "name": (financials.get(code, {}).get("name") if financials else None)
                or code,
                "momentum": style["momentum_60"],
                "low_vol": -risk["annual_vol"],  # 低波为正
                "beta": risk["beta"],
                "sharpe": risk["sharpe"],
            }
            if financials and code in financials:
                fin = financials[code]
                inc = fin["income_statement"]
                bal = fin["balance_sheet"]
                if len(inc) >= 2 and len(bal) >= 2:
                    latest = inc[-1]
                    prev = inc[-2]
                    latest_bal = bal[-1]
                    roe = latest["net_profit"] / latest_bal["equity"] if latest_bal["equity"] else 0.0
                    growth = (latest["revenue"] / prev["revenue"] - 1.0) if prev["revenue"] else 0.0
                    value_proxy = latest["operating_profit"] / latest_bal["total_assets"] if latest_bal["total_assets"] else 0.0
                    row.update(
                        {
                            "quality": round(float(roe), 4),
                            "growth": round(float(growth), 4),
                            "value": round(float(value_proxy), 4),
                        }
                    )
            rows.append(row)

        if not rows:
            return rows

        # 截面 z-score（仅对数值因子）
        factor_keys = ["momentum", "low_vol", "quality", "growth", "value"]
        arr = {k: np.array([r.get(k, 0.0) for r in rows], dtype=float) for k in factor_keys}
        mean = {k: arr[k].mean() for k in factor_keys}
        std = {k: (arr[k].std(ddof=0) or 1.0) for k in factor_keys}
        for r in rows:
            zs = []
            for k in factor_keys:
                z = (r.get(k, 0.0) - mean[k]) / std[k] if std[k] > 0 else 0.0
                r[f"z_{k}"] = round(float(z), 3)
                zs.append(z)
            r["composite_score"] = round(float(np.mean(zs)), 3)
        rows.sort(key=lambda x: x["composite_score"], reverse=True)
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        return rows
