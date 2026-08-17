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
      '并通过 LangGraph 编排 8 类业务工具。\n\n' +
      '当前为 **Demo 模式**（内置样例数据）。如需连接真实后端，请在右上角切换到 Live 模式并填写 API 地址。',
    trace: {
      intent: 'general',
      tool: 'general',
      params: {},
      latencyMs: 0,
      retrieved: [],
    },
  }
}
