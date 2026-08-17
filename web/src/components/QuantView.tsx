import type { UIEvent } from 'react'
import type { QuantData, BacktestData, LeaderRow, ReportData, StockFactor } from '../types'
import { QUANT_DATA } from '../demo/quant'

// 中国习惯：涨=红(rose)，跌=绿(emerald)
function signColor(v: number): string {
  if (v > 0) return 'text-rose'
  if (v < 0) return 'text-emerald-400'
  return 'text-muted'
}
function pct(v: number, d = 2): string {
  return (v * 100).toFixed(d) + '%'
}
function num(v: number, d = 2): string {
  return v.toFixed(d)
}

function KpiRow({ bt }: { bt: BacktestData }) {
  const s = bt.summary
  const items = [
    { label: '累计收益', value: pct(s.total_return_pct / 100), color: signColor(s.total_return_pct) },
    { label: '年化收益', value: pct(s.annual_return_pct / 100), color: signColor(s.annual_return_pct) },
    { label: '夏普比率', value: num(s.sharpe), color: 'text-fg' },
    { label: '最大回撤', value: pct(s.max_drawdown_pct / 100), color: 'text-emerald-400' },
    { label: '胜率', value: pct(s.win_rate_pct / 100, 0), color: 'text-fg' },
    { label: '交易笔数', value: String(s.total_trades), color: 'text-fg' },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {items.map((it) => (
        <div key={it.label} className="rounded-xl border border-line bg-surface/60 px-4 py-3">
          <div className="text-[11px] text-muted">{it.label}</div>
          <div className={`text-xl font-semibold mt-1 ${it.color}`}>{it.value}</div>
        </div>
      ))}
    </div>
  )
}

function Leaderboard({ rows }: { rows: LeaderRow[] }) {
  const zCols: { key: keyof LeaderRow; label: string }[] = [
    { key: 'z_momentum', label: '动量' },
    { key: 'z_value', label: '价值' },
    { key: 'z_quality', label: '质量' },
    { key: 'z_growth', label: '成长' },
    { key: 'z_low_vol', label: '低波' },
  ]
  const maxAbs = Math.max(...rows.flatMap((r) => zCols.map((c) => Math.abs(Number(r[c.key])))), 1)
  return (
    <section>
      <h2 className="text-sm font-semibold text-fg mb-3">多因子综合排行榜（截面 z-score 合成）</h2>
      <div className="rounded-xl border border-line overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface2/70 text-muted text-[11px] uppercase">
              <th className="text-left px-4 py-2">排名</th>
              <th className="text-left px-4 py-2">标的</th>
              {zCols.map((c) => (
                <th key={c.key} className="text-center px-2 py-2">{c.label}</th>
              ))}
              <th className="text-right px-4 py-2">综合得分</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.code} className="border-t border-line/60">
                <td className="px-4 py-2 text-muted">#{r.rank}</td>
                <td className="px-4 py-2">
                  <div className="text-fg font-medium">{r.name}</div>
                  <div className="text-[11px] text-muted font-mono">{r.code}</div>
                </td>
                {zCols.map((c) => {
                  const z = Number(r[c.key])
                  return (
                    <td key={c.key} className="px-2 py-2">
                      <div className="flex items-center justify-center gap-1">
                        <div className="w-14 h-1.5 rounded bg-surface2 overflow-hidden">
                          <div
                            className={`h-full ${z >= 0 ? 'bg-teal' : 'bg-rose'}`}
                            style={{ width: `${(Math.abs(z) / maxAbs) * 100}%`, marginLeft: z >= 0 ? 0 : 'auto', marginRight: z >= 0 ? 'auto' : 0 }}
                          />
                        </div>
                        <span className={`text-[11px] w-8 text-right ${signColor(z)}`}>{num(z)}</span>
                      </div>
                    </td>
                  )
                })}
                <td className="px-4 py-2 text-right">
                  <span className="font-semibold text-teal">{num(r.composite_score)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-muted mt-2">
        因子：动量(Momentum) · 低波(LowVol) · 质量(ROE) · 成长(营收CAGR) · 价值(经营利润率/总资产)；
        各因子截面标准化为 z-score 后等权合成综合得分。
      </p>
    </section>
  )
}

function RiskCards({ stocks }: { stocks: Record<string, StockFactor> }) {
  const list = Object.values(stocks)
  return (
    <section>
      <h2 className="text-sm font-semibold text-fg mb-3">风险因子（基于 {QUANT_DATA.market_name} 的 CAPM）</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.map((s) => {
          const r = s.risk
          const cells: { k: string; v: string; c?: string }[] = [
            { k: '夏普', v: num(r.sharpe), c: 'text-fg' },
            { k: '索提诺', v: num(r.sortino), c: 'text-fg' },
            { k: '最大回撤', v: pct(r.max_drawdown), c: 'text-emerald-400' },
            { k: 'Beta', v: num(r.beta), c: 'text-fg' },
            { k: '年化Alpha', v: pct(r.alpha), c: signColor(r.alpha) },
            { k: '年化波动', v: pct(r.annual_vol), c: 'text-fg' },
            { k: 'VaR95(年)', v: pct(r.var_95_annual), c: 'text-rose' },
            { k: 'CVaR95(年)', v: pct(r.cvar_95_annual), c: 'text-rose' },
            { k: '卡玛', v: num(r.calmar), c: 'text-fg' },
          ]
          return (
            <div key={s.code} className="rounded-xl border border-line bg-surface/60 p-4">
              <div className="flex items-baseline justify-between">
                <div className="text-fg font-medium">{s.name}</div>
                <div className="text-[11px] text-muted font-mono">{s.code}</div>
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-lg font-semibold text-fg">¥{num(s.price, 2)}</span>
                <span className={`text-[11px] ${signColor(s.style.recent_20d_return)}`}>
                  20日 {pct(s.style.recent_20d_return)}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-x-3 gap-y-2 mt-3">
                {cells.map((c) => (
                  <div key={c.k}>
                    <div className="text-[10px] text-muted">{c.k}</div>
                    <div className={`text-sm font-medium ${c.c}`}>{c.v}</div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function RoeBars({ report }: { report: ReportData }) {
  const data = report.ratios
  const max = Math.max(...data.map((d) => d.roe), 0.01)
  return (
    <div className="flex items-end gap-2 h-16">
      {data.map((d) => {
        const h = Math.max((Math.abs(d.roe) / max) * 100, 4)
        return (
          <div key={d.year} className="flex flex-col items-center justify-end flex-1">
            <div
              className={`w-full rounded-t ${d.roe >= 0 ? 'bg-teal/70' : 'bg-rose/70'}`}
              style={{ height: `${h}%` }}
            />
            <span className="text-[10px] text-muted mt-1">{d.year}</span>
          </div>
        )
      })}
    </div>
  )
}

function Reports({ reports }: { reports: Record<string, ReportData> }) {
  const list = Object.values(reports)
  return (
    <section>
      <h2 className="text-sm font-semibold text-fg mb-3">财报分析（三大表 · 财务比率 · 同比趋势 · 异常预警）</h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {list.map((rep) => {
          const lt = rep.latest
          const ratioCells = [
            { k: 'ROE', v: pct(lt.roe) },
            { k: '毛利率', v: pct(lt.gross_margin) },
            { k: '净利率', v: pct(lt.net_margin) },
            { k: '资产负债率', v: pct(lt.debt_to_assets) },
            { k: '流动比率', v: num(lt.current_ratio) },
            { k: '营收同比', v: lt.revenue_yoy == null ? '—' : pct(lt.revenue_yoy), c: lt.revenue_yoy == null ? 'text-muted' : signColor(lt.revenue_yoy) },
          ]
          return (
            <div key={rep.code} className="rounded-xl border border-line bg-surface/60 p-4">
              <div className="flex items-baseline justify-between">
                <div className="text-fg font-medium">{rep.name}</div>
                <div className="text-[11px] text-muted font-mono">{rep.code}</div>
              </div>
              <div className="mt-3">
                <div className="text-[10px] text-muted mb-1">ROE 趋势（{rep.years[0]}–{rep.years[rep.years.length - 1]}）</div>
                <RoeBars report={rep} />
              </div>
              <div className="grid grid-cols-3 gap-x-3 gap-y-2 mt-3">
                {ratioCells.map((c) => (
                  <div key={c.k}>
                    <div className="text-[10px] text-muted">{c.k}</div>
                    <div className={`text-sm font-medium ${'c' in c ? c.c : 'text-fg'}`}>{c.v}</div>
                  </div>
                ))}
              </div>
              {rep.anomaly_count > 0 ? (
                <div className="mt-3 space-y-1">
                  {rep.anomalies.map((a, i) => (
                    <div
                      key={i}
                      className={`text-[11px] px-2 py-1 rounded ${
                        a.level === 'high'
                          ? 'bg-rose/10 text-rose border border-rose/30'
                          : 'bg-amber/10 text-amber border border-amber/30'
                      }`}
                    >
                      ⚠ {a.rule}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-3 text-[11px] px-2 py-1 rounded bg-teal/10 text-teal border border-teal/30">
                  ✓ 未触发异常阈值
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function BacktestNote({ bt }: { bt: BacktestData }) {
  return (
    <section className="rounded-xl border border-line bg-surface/40 p-4">
      <h2 className="text-sm font-semibold text-fg mb-1">因子回测 · {bt.meta.strategy_name}</h2>
      <p className="text-[12px] text-muted leading-relaxed">
        回测区间 {bt.meta.start} ~ {bt.meta.end}，初始资金 ¥{bt.meta.initial_cash.toLocaleString()}，
        A 股（{bt.meta.market}）多空仅做多。信号于第 i 日收盘生成、第 i+1 日开盘撮合（杜绝前视），
        含 120 日 warmup、T+1、次日均价与交易费用，期末强制平仓。
        下方为完整权益曲线 / 回撤 / 交易明细 / 指标解读仪表盘（由「回测明算」专家模板渲染，同源内嵌）。
      </p>
    </section>
  )
}

function BacktestDashboard({ bt }: { bt: BacktestData }) {
  const url = import.meta.env.BASE_URL + 'backtest/momentum_688001SH.html'
  const onLoad = (e: UIEvent<HTMLIFrameElement>) => {
    // 同源：确保仪表盘以暗色呈现，贴合整体 UI
    try {
      const doc = e.currentTarget.contentDocument
      if (doc) {
        doc.documentElement.setAttribute('data-theme', 'dark')
        const apply = () => doc.documentElement.setAttribute('data-theme', 'dark')
        const obs = new MutationObserver(apply)
        obs.observe(doc.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
      }
    } catch {
      /* 跨域安全限制，忽略 */
    }
  }
  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-fg">回测仪表盘（专家模板 · 同源内嵌）</h2>
        <a href={url} target="_blank" rel="noreferrer" className="text-[11px] text-teal hover:underline font-mono">
          新标签打开 ↗
        </a>
      </div>
      <div className="rounded-xl border border-line overflow-hidden bg-surface">
        <iframe
          src={url}
          title={`回测仪表盘 ${bt.meta.symbol}`}
          onLoad={onLoad}
          className="w-full block"
          style={{ height: '1280px', border: 0 }}
        />
      </div>
      <p className="text-[11px] text-muted mt-2">
        策略 {bt.meta.strategy_name}：权益曲线、回撤带、交易明细与指标解读一图尽览；数据由
        <span className="font-mono text-teal"> src/factors/factor_backtest.py </span>真实回测导出。
      </p>
    </section>
  )
}

export default function QuantView() {
  const q: QuantData = QUANT_DATA
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-8">
        <div>
          <h1 className="text-lg font-semibold text-fg">量化因子与财报分析</h1>
          <p className="text-[12px] text-muted mt-1">
            风险因子挖掘 · 多因子排行榜 · 财报三大表解析与异常预警 · 因子策略回测。
            以下数值由 <span className="text-teal">src/factors</span> 引擎在合成数据上真实计算生成。
          </p>
        </div>
        <KpiRow bt={q.backtest} />
        <Leaderboard rows={q.leaderboard} />
        <RiskCards stocks={q.per_stock} />
        <Reports reports={q.reports} />
        <BacktestNote bt={q.backtest} />
        <BacktestDashboard bt={q.backtest} />
      </div>
    </div>
  )
}
