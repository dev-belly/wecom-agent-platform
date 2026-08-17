import { TOOLS } from '../constants'

interface Props {
  activeTool: string | null
}

export default function Sidebar({ activeTool }: Props) {
  return (
    <aside className="w-60 shrink-0 hidden md:flex flex-col border-r border-line bg-surface/40">
      <div className="px-4 py-3 border-b border-line">
        <div className="text-xs text-muted">业务工具</div>
        <div className="text-sm font-medium text-fg">8 类金融查询能力</div>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {TOOLS.map((t) => {
          const active = t.name === activeTool
          return (
            <div
              key={t.name}
              className={`rounded-lg px-3 py-2 border transition ${
                active
                  ? 'border-blue/50 bg-blue/10'
                  : 'border-transparent hover:border-line hover:bg-surface2/50'
              }`}
            >
              <div
                className={`text-sm font-medium ${
                  active ? 'text-blue' : 'text-fg'
                }`}
              >
                {t.label}
              </div>
              <div className="text-[11px] text-muted leading-snug mt-0.5">
                {t.desc}
              </div>
            </div>
          )
        })}
      </div>
      <div className="px-4 py-3 border-t border-line text-[11px] text-muted">
        LangGraph 编排 · 参数自动校验
      </div>
    </aside>
  )
}
