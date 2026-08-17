export interface RetrievedChunk {
  text: string
  score: number
  source: 'bm25' | 'vector' | 'fusion'
  rerankScore?: number
}

export interface TraceInfo {
  intent: string
  tool: string
  params: Record<string, unknown>
  retrieved: RetrievedChunk[]
  latencyMs: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  trace?: TraceInfo
  error?: boolean
}

export interface ToolMeta {
  name: string
  label: string
  desc: string
}

export interface Metrics {
  recallAt10: number
  precisionAt3: number
  lastLatencyMs: number
}

// ── 量化因子 / 财报分析 ──────────────────────────────

export interface RiskMetrics {
  annual_return: number
  annual_vol: number
  sharpe: number
  sortino: number
  max_drawdown: number
  calmar: number
  beta: number
  alpha: number
  var_95_annual: number
  cvar_95_annual: number
  skew: number
  kurtosis: number
}

export interface StockStyle {
  momentum_20: number
  momentum_60: number
  momentum_120: number
  volatility_annual: number
  recent_20d_return: number
}

export interface StockFactor {
  code: string
  name: string
  price: number
  risk: RiskMetrics
  style: StockStyle
}

export interface LeaderRow {
  code: string
  name: string
  momentum: number
  low_vol: number
  beta: number
  sharpe: number
  quality: number
  growth: number
  value: number
  z_momentum: number
  z_low_vol: number
  z_quality: number
  z_growth: number
  z_value: number
  composite_score: number
  rank: number
}

export interface RatioYear {
  year: number
  gross_margin: number
  net_margin: number
  roe: number
  roa: number
  debt_to_assets: number
  current_ratio: number
  quick_ratio: number
  ar_turnover_days: number
  ocf_to_net_profit: number
  revenue_yoy: number | null
  net_profit_yoy: number | null
}

export interface Anomaly {
  level: 'high' | 'mid'
  rule: string
  value: number
}

export interface ReportData {
  code: string
  name: string
  found: boolean
  years: number[]
  ratios: RatioYear[]
  latest: RatioYear
  anomalies: Anomaly[]
  anomaly_count: number
}

export interface BacktestData {
  meta: {
    strategy_name: string
    symbol: string
    start: string
    end: string
    initial_cash: number
    market: string
  }
  summary: {
    total_return_pct: number
    annual_return_pct: number
    max_drawdown_pct: number
    sharpe: number
    win_rate_pct: number
    total_trades: number
  }
}

export interface QuantData {
  market_name: string
  per_stock: Record<string, StockFactor>
  leaderboard: LeaderRow[]
  reports: Record<string, ReportData>
  backtest: BacktestData
}
