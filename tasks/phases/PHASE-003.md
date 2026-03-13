---
phase_id: phase-3
title: 诊断过程可视化（LangSmith）
status: draft
priority: P2
---

## Goal

运维人员和工程师可在 UI 中查看每次 AI 诊断的节点执行轨迹、token 用量和检索源，增强对 AI 决策的信任度。

## In Scope

- LangSmith 追踪集成（LANGCHAIN_TRACING_V2=true 路径）
- 前端诊断溯源面板：节点执行时序 / 检索文档来源 / token 用量统计
- 每次诊断 run_id 透传至前端
- 可选：嵌入 LangSmith trace URL 供工程师深入查看

## Out of Scope

- 生产环境默认开启（央企数据分级要求，默认 disabled，需显式配置）
- LangSmith eval 自动化（独立规划）

## Exit Criteria

- LANGCHAIN_TRACING_V2=true 时，诊断节点轨迹在 LangSmith 可查
- 前端溯源面板展示至少：节点名、耗时、检索文档 top-3
- 生产默认配置 LANGCHAIN_TRACING_V2=false 不影响正常诊断流程

## Dependencies

- PHASE-001（需要 LangGraph pipeline 已稳定）

## Notes

参考 docs/05-langsmith-integration.md。生产数据敏感，开启需申请审批。
