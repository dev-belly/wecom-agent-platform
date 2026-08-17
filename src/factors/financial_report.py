"""财报分析：三大表解析 → 财务比率 → 同比趋势 → 异常预警

输入为结构化三大表（dict，来自 demo_data.load_financials 或真实财报接口），
输出为可直接用于对话 / 看板的指标字典。
"""

from __future__ import annotations

from typing import Any


class FinancialReportAnalyzer:
    """财务健康度与异常检测。"""

    def __init__(self, financials: dict[str, dict]):
        self.financials = financials

    # ── 比率计算 ─────────────────────────────────────
    def ratios(self, code: str) -> list[dict]:
        """逐年度计算核心财务比率。"""
        fin = self.financials.get(code)
        if not fin:
            return []
        inc = fin["income_statement"]
        bal = fin["balance_sheet"]
        cf = fin["cash_flow"]
        out = []
        for i, y in enumerate(fin["years"]):
            row_inc = inc[i]
            row_bal = bal[i]
            row_cf = cf[i]
            rev = row_inc["revenue"]
            gp = row_inc["gross_profit"]
            np_ = row_inc["net_profit"]
            ta = row_bal["total_assets"]
            tl = row_bal["total_liabilities"]
            eq = row_bal["equity"]
            ca = row_bal["current_assets"]
            cl = row_bal["current_liabilities"]
            ar = row_bal["accounts_receivable"]
            inv = row_bal["inventory"]

            gross_margin = gp / rev if rev else 0.0
            net_margin = np_ / rev if rev else 0.0
            roe = np_ / eq if eq else 0.0
            roa = np_ / ta if ta else 0.0
            debt_to_assets = tl / ta if ta else 0.0
            current_ratio = ca / cl if cl else 0.0
            quick_ratio = (ca - inv) / cl if cl else 0.0
            ar_turnover_days = (ar / rev * 365) if rev else 0.0
            ocf_to_np = row_cf["operating_cash_flow"] / np_ if np_ else 0.0

            # 同比
            rev_yoy = (rev / inc[i - 1]["revenue"] - 1.0) if i > 0 and inc[i - 1]["revenue"] else None
            np_yoy = (np_ / inc[i - 1]["net_profit"] - 1.0) if i > 0 and inc[i - 1]["net_profit"] else None

            out.append(
                {
                    "year": y,
                    "gross_margin": round(gross_margin, 4),
                    "net_margin": round(net_margin, 4),
                    "roe": round(roe, 4),
                    "roa": round(roa, 4),
                    "debt_to_assets": round(debt_to_assets, 4),
                    "current_ratio": round(current_ratio, 3),
                    "quick_ratio": round(quick_ratio, 3),
                    "ar_turnover_days": round(ar_turnover_days, 1),
                    "ocf_to_net_profit": round(ocf_to_np, 3),
                    "revenue_yoy": round(rev_yoy, 4) if rev_yoy is not None else None,
                    "net_profit_yoy": round(np_yoy, 4) if np_yoy is not None else None,
                }
            )
        return out

    # ── 异常预警 ─────────────────────────────────────
    def anomalies(self, code: str) -> list[dict]:
        """对最新年度的比率做阈值预警。"""
        rows = self.ratios(code)
        if not rows:
            return []
        latest = rows[-1]
        flags: list[dict] = []

        if latest["debt_to_assets"] > 0.70:
            flags.append({"level": "high", "rule": "资产负债率 > 70%", "value": latest["debt_to_assets"]})
        if latest["current_ratio"] < 1.0:
            flags.append({"level": "high", "rule": "流动比率 < 1.0", "value": latest["current_ratio"]})
        if latest["quick_ratio"] < 0.6:
            flags.append({"level": "mid", "rule": "速动比率 < 0.6", "value": latest["quick_ratio"]})
        if latest["gross_margin"] < 0.20:
            flags.append({"level": "mid", "rule": "毛利率 < 20%", "value": latest["gross_margin"]})
        if latest["ocf_to_net_profit"] < 0.6:
            flags.append({"level": "high", "rule": "经营现金流/净利润 < 0.6（盈利质量弱）", "value": latest["ocf_to_net_profit"]})
        if latest["ar_turnover_days"] > 180:
            flags.append({"level": "mid", "rule": "应收账款周转天数 > 180 天", "value": latest["ar_turnover_days"]})

        # 毛利率同比骤降
        if len(rows) >= 2:
            prev = rows[-2]["gross_margin"]
            if latest["gross_margin"] - prev < -0.05:
                flags.append(
                    {"level": "mid", "rule": "毛利率同比下降 > 5pct", "value": round(latest["gross_margin"] - prev, 4)}
                )
        return flags

    # ── 汇总（对话工具用）────────────────────────────
    def summarize(self, code: str) -> dict[str, Any]:
        fin = self.financials.get(code)
        if not fin:
            return {"code": code, "found": False}
        ratios = self.ratios(code)
        flags = self.anomalies(code)
        latest = ratios[-1] if ratios else {}
        return {
            "code": code,
            "name": fin.get("name", code),
            "found": True,
            "years": fin["years"],
            "ratios": ratios,
            "latest": latest,
            "anomalies": flags,
            "anomaly_count": len(flags),
        }
