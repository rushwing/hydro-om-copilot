---
phase_id: phase-1
title: 手动诊断核心
status: done
priority: P1
---

## Goal

运维人员描述故障现象，AI 返回根因分析（Top-3）+ SOP 检查清单 + 班组交班报告草稿。

## In Scope

- SSE 流式诊断 API（POST /diagnosis/run）
- LangGraph 5 节点 pipeline：symptom_parser / image_agent / retrieval / reasoning / report_gen
- Hybrid RAG：BM25 + Dense + RRF 融合检索
- 前端全流程 UI：InputPanel / StreamingOutput / RootCauseCard / ChecklistPanel / ReportDraft / RiskBadge
- 会话持久化（localStorage）
- 知识库入库流水线（scripts/ingest_kb.py）

## Out of Scope

- 自动传感轮询（属 PHASE-002）
- 鉴权与权限控制（属 PHASE-004）
- 真实传感器接入（属 PHASE-005）

## Exit Criteria

- POST /diagnosis/run 返回完整 DiagnosisResult（root_causes、check_steps、report_draft 字段均非空）
- 前端 SSE 流式渲染全程无断流
- RiskBadge 在深色主题下可见（使用本地 darkRiskColors）

## Dependencies

无（首个业务 phase）

## Notes

已合并至 main 分支。代码已实现并通过手动验证。
