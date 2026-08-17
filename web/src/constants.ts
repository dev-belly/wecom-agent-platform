import type { ToolMeta } from './types'

export const TOOLS: ToolMeta[] = [
  { name: 'contract_query', label: '合同查询', desc: '按编号/甲方/乙方/金额/日期筛选金融合同' },
  { name: 'product_nav', label: '产品净值', desc: '查询单位净值、累计净值、日增长率' },
  { name: 'customer_holding', label: '客户持仓', desc: '查询客户持仓份额与市值汇总' },
  { name: 'product_info', label: '产品信息', desc: '产品代码、类型、风险等级、费率等基本信息' },
  { name: 'fee_query', label: '费率查询', desc: '管理费、托管费、申购赎回费' },
  { name: 'risk_query', label: '风险等级', desc: '产品或客户风险评估信息' },
  { name: 'custody_bank', label: '托管银行', desc: '产品托管银行与账户信息' },
  { name: 'fund_manager', label: '基金管理人', desc: '基金管理人/产品管理人信息' },
]

export function toolLabel(name: string): string {
  return TOOLS.find((t) => t.name === name)?.label ?? name
}
