import type { Message, TraceInfo } from '../types'

interface DemoResult {
  content: string
  trace: TraceInfo
}

// 演示用样例响应（无需后端即可交互）
const SCENARIOS: { match: RegExp; build: (q: string) => DemoResult }[] = [
  {
    match: /合同|HT\d|甲方|乙方|签约/,
    build: () => ({
      content:
        '已为您查询到合同 **HT20240315001** 的关键信息：\n\n' +
        '- **合同编号**：HT20240315001\n' +
        '- **甲方（管理人）**：星辰资产管理有限公司\n' +
        '- **乙方（托管行）**：招商银行上海分行\n' +
        '- **产品名称**：星辰稳健增益 1 号集合资产管理计划\n' +
        '- **合同金额**：¥ 120,000,000.00\n' +
        '- **签约日期**：2024-03-15\n' +
        '- **期限**：18 个月\n\n' +
        '该合同已通过 BM25 + 向量混合检索定位，来源 PDF 第 3、4 页跨页表格。',
      trace: {
        intent: 'contract_query',
        tool: 'contract_query',
        params: { contract_id: 'HT20240315001' },
        latencyMs: 412,
        retrieved: [
          { text: '合同编号:HT20240315001 | 甲方:星辰资产 | 乙方:招商银行 | 金额:120000000', score: 0.92, source: 'fusion', rerankScore: 0.87 },
          { text: '合同编号:HT20240315001 | 产品:星辰稳健增益1号 | 期限:18个月 | 签约日:2024-03-15', score: 0.88, source: 'fusion', rerankScore: 0.83 },
          { text: '合同编号:HT20240315001 | 托管行:招商银行上海分行 | 费率:0.15%/年', score: 0.81, source: 'bm25', rerankScore: 0.79 },
        ],
      },
    }),
  },
  {
    match: /净值|NAV|单位净值|累计净值/,
    build: () => ({
      content:
        '产品 **XYZ123（星辰稳健增益 1 号）** 最新净值如下：\n\n' +
        '- **单位净值**：1.0427\n' +
        '- **累计净值**：1.0589\n' +
        '- **日增长率**：+0.34%\n' +
        '- **净值日期**：2026-08-14\n\n' +
        '数据经 Dense Vector 语义召回命中产品要素表，并由 Reranker 重排确认。',
      trace: {
        intent: 'product_nav',
        tool: 'product_nav',
        params: { product_code: 'XYZ123' },
        latencyMs: 386,
        retrieved: [
          { text: '产品代码:XYZ123 | 单位净值:1.0427 | 累计净值:1.0589 | 日期:2026-08-14', score: 0.9, source: 'fusion', rerankScore: 0.88 },
          { text: '产品代码:XYZ123 | 日增长率:+0.34% | 年化:4.21%', score: 0.84, source: 'vector', rerankScore: 0.82 },
          { text: '产品代码:XYZ123 | 风险等级:R3 | 类型:集合资管', score: 0.77, source: 'bm25', rerankScore: 0.74 },
        ],
      },
    }),
  },
  {
    match: /持仓|客户|份额|市值/,
    build: () => ({
      content:
        '客户 **C2024001（陈晓）** 当前持仓汇总：\n\n' +
        '- **持仓产品数**：3 只\n' +
        '- **总市值**：¥ 2,847,500.00\n' +
        '- **明细**：\n' +
        '  - 星辰稳健增益 1 号：份额 1,200,000，市值 ¥ 1,251,240\n' +
        '  - 安心债基 A：份额 800,000，市值 ¥ 824,000\n' +
        '  - 量化对冲 2 号：份额 600,000，市值 ¥ 772,260\n\n' +
        '持仓信息通过客户持仓工具跨多份 PDF 聚合得到。',
      trace: {
        intent: 'customer_holding',
        tool: 'customer_holding',
        params: { customer_id: 'C2024001' },
        latencyMs: 433,
        retrieved: [
          { text: '客户:C2024001 | 产品:XYZ123 | 份额:1200000 | 市值:1251240', score: 0.89, source: 'fusion', rerankScore: 0.85 },
          { text: '客户:C2024001 | 产品:ANX01 | 份额:800000 | 市值:824000', score: 0.85, source: 'fusion', rerankScore: 0.81 },
          { text: '客户:C2024001 | 产品:LH002 | 份额:600000 | 市值:772260', score: 0.8, source: 'vector', rerankScore: 0.78 },
        ],
      },
    }),
  },
  {
    match: /风险因子|Beta|Sharpe|索提诺|最大回撤|VaR|波动率/,
    build: () => ({
      content:
        '**星辰科技（688001.SH）** 风险因子测算（基准：合成沪深300）：\n\n' +
        '- **年化收益**：+49.83%　**年化波动**：29.23%\n' +
        '- **夏普比率**：1.50　**索提诺比率**：1.55\n' +
        '- **最大回撤**：-31.41%　**卡玛比率**：1.59\n' +
        '- **Beta**：1.12　**年化 Alpha**：+48.86%\n' +
        '- **VaR95（年）**：-43.9%　**CVaR95（年）**：-57.6%\n\n' +
        '高 Beta + 高波动 + 高夏普，属高弹性成长风格；VaR 提示极端日下行可达四成以上，需配合仓位管理。',
      trace: {
        intent: 'risk_factor_query',
        tool: 'risk_factor_query',
        params: { code: '688001.SH' },
        latencyMs: 358,
        retrieved: [
          { text: '风险因子 | Beta:1.12 | Sharpe:1.50 | MaxDD:-31.41%', score: 0.91, source: 'fusion', rerankScore: 0.88 },
          { text: '风险因子 | VaR95:-43.9% | CVaR95:-57.6% | Calmar:1.59', score: 0.86, source: 'vector', rerankScore: 0.84 },
          { text: '风险因子 | vol:29.23% | Sortino:1.55 | Alpha:+48.86%', score: 0.82, source: 'bm25', rerankScore: 0.80 },
        ],
      },
    }),
  },
  {
    match: /财报|ROE|毛利率|资产负债率|流动比率|三大表/,
    build: () => ({
      content:
        '**远创新能（300750.SZ）** 财报分析（2022–2025）：\n\n' +
        '- **最新毛利率**：16.99%　**净利率**：-2.57%\n' +
        '- **ROE**：-3.37%　**资产负债率**：47.93%\n' +
        '- **流动比率**：1.48　**经营现金流/净利润**：1.14\n' +
        '- **营收同比**：+23.51%　**净利润同比**：+144.3%\n\n' +
        '⚠ **异常预警**：毛利率 < 20%（盈利空间偏薄）。营收高增但净利率仍为负，处于盈利修复早期，需关注毛利率能否回升。',
      trace: {
        intent: 'financial_report_query',
        tool: 'financial_report_query',
        params: { code: '300750.SZ' },
        latencyMs: 401,
        retrieved: [
          { text: '财报 | 300750.SZ | 毛利率:16.99% | 净利率:-2.57%', score: 0.9, source: 'fusion', rerankScore: 0.87 },
          { text: '财报 | ROE:-3.37% | 资产负债率:47.93% | 流动比率:1.48', score: 0.85, source: 'vector', rerankScore: 0.82 },
          { text: '财报 | 异常:毛利率<20% | 营收同比:+23.51%', score: 0.81, source: 'bm25', rerankScore: 0.78 },
        ],
      },
    }),
  },
  {
    match: /因子挖掘|因子|排行榜|多因子|选股/,
    build: () => ({
      content:
        '**多因子综合排行榜**（动量 / 价值 / 质量 / 成长 / 低波，截面 z-score 合成）：\n\n' +
        '| 排名 | 标的 | 综合得分 |\n' +
        '| --- | --- | --- |\n' +
        '| #1 | 黔风白酒 | +0.95 |\n' +
        '| #2 | 星辰科技 | +0.72 |\n' +
        '| #3 | 平安保融 | -0.26 |\n' +
        '| #4 | 五粮醇香 | -0.68 |\n' +
        '| #5 | 远创新能 | -0.76 |\n\n' +
        '黔风白酒在价值、质量、低波三项占优，星辰科技动量最强，二者综合领先。详见顶部「量化分析」视图。',
      trace: {
        intent: 'factor_mining',
        tool: 'factor_mining',
        params: {},
        latencyMs: 372,
        retrieved: [
          { text: '因子挖掘 | 黔风白酒 综合+0.95 | 价值z+1.18 质量z+1.17', score: 0.88, source: 'fusion', rerankScore: 0.85 },
          { text: '因子挖掘 | 星辰科技 综合+0.72 | 动量z+1.07', score: 0.84, source: 'vector', rerankScore: 0.81 },
          { text: '因子挖掘 | 远创新能 综合-0.76 | 成长z+0.73', score: 0.79, source: 'bm25', rerankScore: 0.76 },
        ],
      },
    }),
  },
]

const FALLBACK: DemoResult = {
  content:
    '您好，我是企微智能运营 Agent。我可以帮您查询金融合同、产品净值、客户持仓等信息。\n\n' +
    '试试问：\n- “查询合同 HT20240315001 的信息”\n- “星辰稳健增益 1 号最新净值是多少”\n- “客户 C2024001 的持仓情况”',
  trace: {
    intent: 'general',
    tool: 'general',
    params: {},
    latencyMs: 95,
    retrieved: [],
  },
}

export function getDemoReply(query: string): DemoResult {
  for (const s of SCENARIOS) {
    if (s.match.test(query)) return s.build(query)
  }
  return FALLBACK
}

export function welcomeMessage(): Message {
  return {
    id: 'welcome',
    role: 'assistant',
    content:
      '👋 欢迎使用 **企微智能运营 Agent 平台**（演示模式）。\n\n' +
      '本平台面向金融合同与产品要素查询，底层为 BM25 + Dense Vector + Rerank 混合检索链路，' +
      '并通过 LangGraph 编排 11 类业务工具（含风险因子、财报分析、因子挖掘）。\n\n' +
      '点击右上角 **「量化分析」** 可查看多因子排行榜、风险因子卡片与财报可视化；' +
      '或直接提问：「星辰科技的风险因子」「远创新能的财报」「因子排行榜」。',
    trace: {
      intent: 'general',
      tool: 'general',
      params: {},
      latencyMs: 0,
      retrieved: [],
    },
  }
}
