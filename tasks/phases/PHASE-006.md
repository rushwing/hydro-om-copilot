---
phase_id: phase-6
title: 多用户租用（Multi-tenant）
status: draft
priority: P3
---

## Goal

平台支持多个电厂/班组以租户粒度隔离数据与配置。

## In Scope

- 租户注册与管理（租户 ID、电厂名称、配置）
- 数据隔离：知识库、诊断历史、传感器数据按租户分区
- 租户级配置：LLM 参数、告警门限、SOP 模板
- 超级管理员跨租户管理视图
- 向量存储多租户分区（ChromaDB collection 或 Qdrant namespace）

## Out of Scope

- 计费与用量统计（视商业化需求另立 phase）
- 公有云 SaaS 部署（当前目标为私有部署）

## Exit Criteria

- 租户 A 无法查看租户 B 的诊断记录（隔离测试通过）
- 新租户入驻流程可在 UI 完成，无需直接操作数据库
- 向量存储按租户分区后检索结果不串用

## Dependencies

- PHASE-004（多租户依赖鉴权体系）

## Notes

多租户改造对数据库 schema 和向量存储影响较大，建议在 PHASE-004 完成后进行详细技术评审再立项。
