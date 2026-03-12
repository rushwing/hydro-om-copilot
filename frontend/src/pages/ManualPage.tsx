// ── Step node ─────────────────────────────────────────────────────────────────

interface StepNodeProps {
  icon: string;
  label: string;
  desc?: string;
  color: string;
  badge?: string;
  badgeColor?: string;
}

function StepNode({ icon, label, desc, color, badge, badgeColor }: StepNodeProps) {
  return (
    <div className={`rounded-lg border px-4 py-3 text-center ${color}`}>
      <div className="text-xl mb-1">{icon}</div>
      <div className="text-xs font-semibold leading-tight">{label}</div>
      {desc && <div className="text-[10px] opacity-70 mt-1 leading-snug">{desc}</div>}
      {badge && (
        <span className={`inline-block mt-1.5 text-[9px] px-1.5 py-0.5 rounded border font-display uppercase tracking-wide ${badgeColor}`}>
          {badge}
        </span>
      )}
    </div>
  );
}

function DownArrow({ className = "" }: { className?: string }) {
  return (
    <div className={`flex justify-center text-text-muted text-lg leading-none ${className}`}>↓</div>
  );
}

function MergeArrow() {
  return (
    <div className="relative flex items-center justify-center my-2 h-8">
      {/* Left arm */}
      <div className="absolute left-[25%] right-[50%] h-px bg-surface-border top-0" />
      {/* Right arm */}
      <div className="absolute left-[50%] right-[25%] h-px bg-surface-border top-0" />
      {/* Vertical drop */}
      <div className="absolute left-[50%] -translate-x-px w-px h-full bg-surface-border" />
      {/* Down chevron */}
      <div className="absolute bottom-0 left-1/2 -translate-x-2.5 text-text-muted text-sm leading-none">↓</div>
    </div>
  );
}

function ForkArrow() {
  return (
    <div className="relative flex items-center justify-center my-2 h-8">
      {/* Vertical rise */}
      <div className="absolute left-[50%] -translate-x-px w-px h-full bg-surface-border" />
      {/* Left arm */}
      <div className="absolute left-[25%] right-[50%] h-px bg-surface-border bottom-0" />
      {/* Right arm */}
      <div className="absolute left-[50%] right-[25%] h-px bg-surface-border bottom-0" />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ManualPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-8 space-y-8">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-wide text-text-primary mb-1">
          操作手册
        </h1>
        <p className="text-xs text-text-muted">水电机组智能运维系统 · 工程师操作规程</p>
      </div>

      {/* Section 1: Two-path DAG */}
      <section className="rounded-lg border border-surface-border bg-surface-card p-6">
        <h2 className="font-display text-sm uppercase tracking-widest text-text-muted mb-6 flex items-center gap-2">
          故障处置流程图
          <div className="flex-1 h-px bg-surface-border" />
        </h2>

        {/* Two diverging paths */}
        <div className="grid grid-cols-2 gap-6">
          {/* Left: Manual diagnosis path */}
          <div className="space-y-1">
            <div className="text-center mb-3">
              <span className="text-xs font-display uppercase tracking-widest text-blue-400 border border-blue-800/50 bg-blue-950/30 px-3 py-1 rounded-full">
                人工诊断路径
              </span>
            </div>
            <StepNode
              icon="📝"
              label="故障现象录入"
              desc="工程师描述异常现象、选择机组与故障类型"
              color="border-blue-800/60 bg-blue-950/30 text-blue-300"
            />
            <DownArrow />
            <StepNode
              icon="🤖"
              label="AI 诊断分析"
              desc="流式生成根因分析、SOP 检查清单与报告草稿"
              color="border-amber/30 bg-amber/10 text-amber"
              badge="实时流式"
              badgeColor="border-amber/30 bg-amber/10 text-amber"
            />
          </div>

          {/* Right: Auto diagnosis path */}
          <div className="space-y-1">
            <div className="text-center mb-3">
              <span className="text-xs font-display uppercase tracking-widest text-red-400 border border-red-800/50 bg-red-950/30 px-3 py-1 rounded-full">
                自动诊断路径
              </span>
            </div>
            <StepNode
              icon="⚠"
              label="传感器告警"
              desc="振动/油压/温升传感器读数超过报警阈值"
              color="border-red-800/60 bg-red-950/30 text-red-400"
            />
            <DownArrow />
            <StepNode
              icon="🤖"
              label="AI 自动诊断"
              desc="后台自动触发，冷却期内同机组不重复诊断"
              color="border-amber/30 bg-amber/10 text-amber"
              badge="后台自动"
              badgeColor="border-amber/30 bg-amber/10 text-amber"
            />
          </div>
        </div>

        {/* Merge point */}
        <MergeArrow />

        {/* Shared steps */}
        <div className="max-w-xs mx-auto space-y-1">
          <StepNode
            icon="📋"
            label="报告审阅"
            desc="查看根因分析结果与风险等级评估"
            color="border-surface-border bg-surface-elevated text-text-primary"
          />
          <DownArrow />
          <StepNode
            icon="✅"
            label="SOP 逐项确认"
            desc="逐项勾选检查操作规程，状态自动保存"
            color="border-surface-border bg-surface-elevated text-text-primary"
            badge="全部打勾后解锁"
            badgeColor="border-amber/30 bg-amber/10 text-amber"
          />
          <DownArrow />
          <StepNode
            icon="✍"
            label="填写人工处理报告"
            desc="记录现场处理过程、处置结果及后续建议"
            color="border-surface-border bg-surface-elevated text-text-primary"
          />
        </div>

        {/* Fork point */}
        <ForkArrow />

        {/* Two outcomes */}
        <div className="grid grid-cols-2 gap-6 mt-0">
          <StepNode
            icon="✓"
            label="提交归档"
            desc="故障已消缺，进入「已归档」记录"
            color="border-emerald-800/60 bg-emerald-950/30 text-emerald-400"
            badge="需完成 SOP + 报告"
            badgeColor="border-emerald-800/50 bg-emerald-950/30 text-emerald-400"
          />
          <StepNode
            icon="⏳"
            label="稍后处理"
            desc="暂存至「待处理」队列，可随时回来继续完成"
            color="border-surface-border bg-surface-elevated text-text-secondary"
          />
        </div>

        {/* Final state */}
        <DownArrow className="mt-1" />
        <div className="max-w-xs mx-auto">
          <StepNode
            icon="🗂"
            label="历史记录 · 已归档"
            desc="所有已消缺故障归档留存，支持人工备注查阅"
            color="border-surface-border bg-surface-card text-text-muted"
          />
        </div>
      </section>

      {/* Section 2: Fault Lifecycle */}
      <section className="rounded-lg border border-surface-border bg-surface-card p-6">
        <h2 className="font-display text-sm uppercase tracking-widest text-text-muted mb-6 flex items-center gap-2">
          故障生命周期
          <div className="flex-1 h-px bg-surface-border" />
        </h2>
        <div className="relative pl-6">
          {/* Vertical line */}
          <div className="absolute left-2 top-0 bottom-0 w-px bg-surface-border" />

          {[
            {
              phase: "正常运行",
              code: "NORMAL",
              color: "border-emerald-800 bg-emerald-950/30 text-emerald-400",
              dot: "bg-emerald-500",
              desc: "所有传感器读数在阈值范围内，系统周期性采集数据。",
            },
            {
              phase: "预警阶段",
              code: "PRE_FAULT",
              color: "border-amber/30 bg-amber/10 text-amber",
              dot: "bg-amber-500",
              desc: "传感器读数进入告警区间，系统开始追踪趋势变化并准备触发诊断。",
            },
            {
              phase: "故障确认",
              code: "FAULT",
              color: "border-red-800 bg-red-950/30 text-red-400",
              dot: "bg-red-500",
              desc: "传感器触发报警阈值，自动诊断流程启动，AI 生成根因分析与 SOP 报告。",
            },
            {
              phase: "冷却等待",
              code: "COOL_DOWN",
              color: "border-blue-800 bg-blue-950/30 text-blue-400",
              dot: "bg-blue-500",
              desc: "同一机组诊断完成后进入冷却期（默认 300s），避免重复触发。",
            },
            {
              phase: "归档完成",
              code: "ARCHIVED",
              color: "border-surface-border bg-surface-elevated text-text-muted",
              dot: "bg-surface-border",
              desc: "工程师审阅并完成现场处置后，将报告标记完成并归档。",
            },
          ].map((item) => (
            <div key={item.code} className="relative mb-5 last:mb-0">
              <div
                className={`absolute -left-4 top-3 w-3 h-3 rounded-full ${item.dot} border-2 border-surface`}
              />
              <div className={`rounded-lg border px-4 py-3 ml-2 ${item.color}`}>
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-medium text-sm">{item.phase}</span>
                  <span className="font-mono text-xs opacity-60">{item.code}</span>
                </div>
                <p className="text-xs opacity-80 leading-relaxed">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Section 3: Responsibility Matrix */}
      <section className="rounded-lg border border-surface-border bg-surface-card p-6">
        <h2 className="font-display text-sm uppercase tracking-widest text-text-muted mb-6 flex items-center gap-2">
          工程师职责矩阵
          <div className="flex-1 h-px bg-surface-border" />
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="text-left py-3 pr-6 font-display text-xs uppercase tracking-wider text-text-muted">
                  职责
                </th>
                {["值班工程师", "技术主管", "系统 AI"].map((role) => (
                  <th
                    key={role}
                    className="text-center py-3 px-4 font-display text-xs uppercase tracking-wider text-text-muted"
                  >
                    {role}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {[
                { duty: "实时监控", values: ["✓", "—", "✓"] },
                { duty: "初步诊断", values: ["—", "—", "✓"] },
                { duty: "报告审阅", values: ["✓", "—", "—"] },
                { duty: "SOP 逐项确认", values: ["✓", "—", "—"] },
                { duty: "填写人工报告", values: ["✓", "—", "—"] },
                { duty: "升级决策", values: ["✓", "✓", "—"] },
                { duty: "归档记录", values: ["✓", "—", "—"] },
              ].map((row) => (
                <tr key={row.duty} className="hover:bg-surface-elevated/50 transition-colors">
                  <td className="py-3 pr-6 text-text-primary font-medium text-sm">{row.duty}</td>
                  {row.values.map((val, i) => (
                    <td key={i} className="py-3 px-4 text-center">
                      {val === "✓" ? (
                        <span className="text-emerald-400 font-bold text-base">✓</span>
                      ) : (
                        <span className="text-text-muted text-xs">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
