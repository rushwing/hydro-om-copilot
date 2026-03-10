> **适用场景**：修改前端组件样式、新增 UI 组件、Tailwind 颜色/字体系统时

# 前端设计系统：工业 HMI 暗色主题

## 1. 设计定位

**目标**：工业精密仪器美学 — 类 DCS/SCADA 控制室的现代 SaaS 品质。
**语境**：高风险故障诊断，操作人员在高压环境下快速读取信息，视觉语言须传达「精密、可靠、专业」。

与通用 SaaS 产品的关键差异：
- 结构化参数输入（机组/设备/异常类型选择器）而非纯聊天框，体现领域专用诊断工具定位
- 琥珀色作为工业安全语言主色（对应现实中仪表盘警示色）
- 高信息密度布局，右侧结果面板可同时展示 5 个模块

---

## 2. 颜色系统（`tailwind.config.ts`）

### 2.1 Surface 层级

| Token | 颜色值 | 用途 |
|-------|--------|------|
| `surface` | `#0a0f1a` | 页面底色、`body` |
| `surface-card` | `#0f1928` | 卡片背景（导航栏、结果卡片）|
| `surface-elevated` | `#162032` | 次级背景（输入框、代码块、进度条背景）|
| `surface-border` | `#1e3a5f` | 所有分隔线、边框 |

层级关系：`surface < surface-card < surface-elevated`，越「高」的元素越亮。

### 2.2 琥珀色 Accent

| Token | 颜色值 | 用途 |
|-------|--------|------|
| `amber` / `amber-500` | `#f59e0b` | 主 accent：选中态、进度条、按钮 |
| `amber-glow` / `amber-400` | `#fbbf24` | Hover 高光 |
| `amber-dim` / `amber-800` | `#92400e` | 禁用态、低对比场景 |

Glow 效果通过 CSS 变量实现（`index.css`）：
```css
--amber-glow: 0 0 12px rgba(245, 158, 11, 0.4);
--amber-glow-strong: 0 0 20px rgba(245, 158, 11, 0.6);
```

### 2.3 文字层级

| Token | 颜色值 | 用途 |
|-------|--------|------|
| `text-primary` | `#e2e8f0` | 主体文字 |
| `text-secondary` | `#94a3b8` | 次要文字、描述 |
| `text-muted` | `#475569` | 占位符、标签、时间戳 |

### 2.4 风险等级色（本地定义，不从 store 读取）

> **重要**：`diagnosisStore.ts` 导出的 `riskLevelColor` 是浅色主题 Tailwind 类，不可在深色主题中直接使用。各组件需本地定义 `darkRiskColors`。

| 风险等级 | 文字色 | 背景色 | 边框色 | 特效 |
|---------|--------|--------|--------|------|
| `low` | `emerald-400` | `emerald-950` | `emerald-800` | — |
| `medium` | `amber` | `amber-950` | `amber-800` | — |
| `high` | `orange-400` | `orange-950` | `orange-800` | — |
| `critical` | `red-400` | `red-950` | `red-800` | `critical-pulse` 动画 |

---

## 3. 字体系统

| 变量 | 字体 | 用途 |
|------|------|------|
| `font-display` | Rajdhani (400/500/600/700) | 技术标签、编号、章节头、按钮文字 |
| `font-sans` | Noto Sans SC (400/500) | 中文正文、描述、诊断内容 |
| `font-mono` | JetBrains Mono (400/500) | 报告内容、知识库引用 ID、流式输出 |

字体通过 `index.css` 顶部 Google Fonts `@import` 加载，生产环境如需离线可换为本地 font-face。

**Rajdhani 用法规范**：
- 章节标题：`font-display text-xs uppercase tracking-widest text-text-muted`
- 卡片编号：`font-display text-lg font-bold text-amber`
- 步骤标签：`font-display text-xs font-bold tracking-wider`

---

## 4. 布局结构

### 4.1 顶级页面布局

```
<Nav />                     ← sticky top-0, h-[52px], bg-surface-card
<div flex h-[calc(100vh-52px)]>
  <aside w-5/12 sticky>     ← 输入 + 流式输出
  <main  w-7/12 scroll>     ← 诊断结果 5 模块
</div>
```

导航栏高度为 **52px**（`py-3` + 内容），`h-[calc(100vh-52px)]` 确保双列高度精准填满视口，两侧各自独立滚动。

### 4.2 输入面板卡片

```
border-l-2 border-l-amber   ← 左侧琥珀色边框作为视觉锚点
bg-surface-card
```

---

## 5. 组件规范

### 5.1 InputPanel — 结构化参数输入

层级从上到下：
1. **机组编号** — 按钮组（#1机 ~ #4机），单选可取消
2. **设备部件** — 单选 chips（6 个部件）
3. **异常类型** — 多选 chips（7 种异常）
4. **建议填充栏** — 当有选中项且输入框为空时展示，点击「填入描述」写入模板文字
5. **异常描述** — `textarea`，amber focus ring
6. **截图上传** — 拖拽区 / 点击；有图片时显示缩略图 + 删除按钮
7. **提交 / 停止** — 全宽 amber 按钮 / 红色停止按钮

Chip 状态：
```
inactive: border-surface-border bg-surface-elevated text-text-secondary
active:   border-amber bg-amber/10 text-amber
```

**关键**：`unit_id` 字段来自 `selectedUnit` state（字符串如 `"#1机"`），直接传入 `DiagnosisRequest.unit_id`；不写入 query 文本。

### 5.2 StreamingOutput — 流水线可视化

```
[symptom_parser] —— [image_agent] —— [retrieval] —— [reasoning] —— [report_gen]
```

节点状态：
- `done`：`bg-amber border-amber`（实心琥珀）
- `active`：`bg-amber/20 border-amber node-active`（带 pulse 动画）
- `pending`：`bg-surface-elevated border-surface-border`（空心灰）

连接线：done 节点后的线段变为 `bg-amber`，未完成保持 `bg-surface-border`。

流式文本区域应用 `.scan-line` CSS class（3s 扫描光效）。

### 5.3 RootCauseCard — 工业卡片

```
border-l-4 border-l-amber     ← 左侧加粗边框
[01] 标题                       ← Rajdhani 字体编号
████████░░ 82%                  ← 块状进度条（10块，每块=10%）
▸ 证据条目                       ← amber 箭头
⚠ 待确认参数                     ← amber 警告框
```

概率条用字符拼接：`Array.from({length:10}, (_,i) => i < filled ? '█' : '░').join('')`

### 5.4 ChecklistPanel — SOP 格式

每步结构：
```
[自定义checkbox]  STEP 01   操作描述
                  预期结果（可选）
                  ⚠ CAUTION: 注意事项（红色框，可选）
```

完成后：行背景变 `emerald-950/20`，文字 `line-through opacity-50`。

底部进度条：`X / Y 步骤已完成`，amber 填充。

### 5.5 RiskBadge

从不引用 `diagnosisStore.riskLevelColor`（浅色主题），始终使用本地 `darkRiskColors` mapping。

### 5.6 ReportDraft — 正式文档

顶部 header 区域：报告标题 + 日期时间 + `sessionId.slice(0,8)`
正文：`font-mono` 等宽字体
底部 footer：AI 生成免责声明
复制按钮：amber → emerald 成功态

---

## 6. 动画规范（`index.css`）

| Class | 效果 | 用途 |
|-------|------|------|
| `.scan-line` | 3s 琥珀扫描光 | 流式输出文本区域 |
| `.node-active` | 节点 pulse（1.5s） | 当前执行中的流水线节点 |
| `.critical-pulse` | 红色边框闪烁（1s） | `critical` 级别风险徽章 |
| `.animate-result` | fade-slide-up（0.35s） | 结果模块出现动画 |

**结果模块交错动画**：通过 inline `style={{ animationDelay: '...s', opacity: 0 }}` 实现，各模块延迟间隔约 50-80ms。

---

## 7. 历史页面

- 空态：居中 ⚡ 图标（`opacity-10`）+ `font-display uppercase tracking-widest`
- 记录卡片：`border-l-2 border-l-surface-border hover:border-l-amber`（hover 时左侧亮起）
- 风险徽章：同 `darkRiskColors` mapping

---

## 8. 设计约束

1. **不修改 `diagnosisStore.ts`** — `riskLevelColor` 导出保留（历史兼容），但深色主题组件不使用
2. **不新增 npm 包** — 所有 UI 用 Tailwind + CSS variables 实现，不引入 Framer Motion 等动画库
3. **字体 fallback** — `font-display` 定义为 `['Rajdhani', 'sans-serif']`，Google Fonts 加载失败时降级为系统 sans-serif
4. **中文字体** — Noto Sans SC 作为 `font-sans`，确保所有中文诊断内容可读性
5. **无障碍** — checkbox 自定义实现须保留 `aria-label`
