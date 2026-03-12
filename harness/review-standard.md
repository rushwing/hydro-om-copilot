---
harness_id: REV-STD-001
component: code review / PR quality
owner: Engineering
version: 0.1
status: stub
last_reviewed: 2026-03-12
---

# Harness Standard — 代码审查规程 [STUB]

> **当前状态：stub。** 已知原则已记录，可作为临时执行依据。
> 完整规程待 openai_codex 在实际 review 中积累模式后补充。

---

## 已确定原则

### PR 提交前（作者自检，claude_code）

- [ ] 本地测试全通过：`bash scripts/local/test.sh`
- [ ] `test_case_ref` 中所有 TC 对应测试通过
- [ ] 无遗留调试代码（`console.log`、`print`、`breakpoint()`）
- [ ] 无硬编码密钥、测试凭证或生产配置
- [ ] `tasks/features/REQ-xxx.md` 已更新为 `status: review`

### Review 关注点（openai_codex）

**契约一致性**
- [ ] 实现与 REQ-xxx.md `Acceptance Criteria` 逐条对应
- [ ] Pydantic 模型字段 ↔ `frontend/src/types/diagnosis.ts` 对齐
- [ ] API 路由路径和方法与前端 fetch 调用一致

**安全性**
- [ ] 无 XSS 风险（前端动态渲染）
- [ ] 无 SQL/命令注入风险
- [ ] 无敏感数据写入日志或 SSE 流

**测试质量**
- [ ] 测试覆盖关键分支，不只是 happy path
- [ ] mock 策略符合 testing-standard.md §3

**代码可读性**
- [ ] 命名清晰，无缩写歧义
- [ ] 复杂逻辑有注释说明 why，而非 what

### HITL 合并条件

- [ ] openai_codex review 无 blocking comment
- [ ] CI 检查通过（当前手动验证，见 ci-standard stub）
- [ ] 人工确认（PR merge 不允许自动化）

---

## 待补充

- [ ] 正式 review checklist 模板（含评分标准）
- [ ] blocking vs non-blocking comment 区分规则
- [ ] 特殊场景处理：hotfix、文档 PR、依赖升级 PR
- [ ] review 时间 SLA

---

## 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始 stub；记录已知 PR 提交前检查、review 关注点和 HITL 合并条件 |
