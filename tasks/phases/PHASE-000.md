---
phase_id: phase-0
title: 平台工程与 Harness
status: in_progress
priority: P0
---

## Goal

建立多 Agent 协作开发基础设施，使 claude_code 和 openai_codex 能在统一规范下自主认领、实现、测试和交付需求。

## In Scope

- Harness 治理文档（requirement-standard / testing-standard / bug-standard / review-standard / ci-standard）
- harness.sh CLI 编排器
- 本地开发脚本（env-setup / dev / build / test / ingest）
- Docker + K8s 部署栈
- Agent workspace（SOUL.md、MEMORY.md）
- tasks/ 目录规范与 Phase/Feature 文档模板

## Out of Scope

- 业务功能实现（属于 PHASE-001 及以上）

## Exit Criteria

- GitHub Actions agent-loop.yml 补全并通过 CI
- vitest 与 Playwright 安装并可执行前端测试
- review-standard.md 与 ci-standard.md 从 stub 升级为 active
- harness-index.md 与所有 standard 文档内部一致性通过审查

## Dependencies

无（横切基础设施，无前置业务 phase）

## Notes

当前完成度约 95%。主要缺口：GitHub Actions 工作流未补全、前端测试工具链（vitest/Playwright）尚未安装。此 phase 横跨整个项目生命周期，持续维护。
