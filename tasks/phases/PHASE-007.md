---
phase_id: phase-7
title: 在线派发故障消缺工单（移动端）
status: draft
priority: P3
---

## Goal

诊断完成后可一键生成并派发工单至手机 App，形成从感知到闭环的完整运维链路。

## In Scope

- 工单生成：基于诊断报告自动填充工单模板（故障描述、建议措施、负责人）
- 工单派发 API（POST /workorder/dispatch）
- 移动端工单接收与确认（响应式 Web App 或原生 App TBD）
- 工单状态追踪：待处理 / 处理中 / 已关闭
- 工单与诊断记录双向关联

## Out of Scope

- ERP/EAM 系统集成（视现场系统另立任务）
- 工单审批流（视业务复杂度另立 phase）

## Exit Criteria

- 诊断完成后 UI 呈现"派发工单"入口，一键提交后工单状态可追踪
- 移动端（≥375px）可正常查看并确认工单
- 工单与对应诊断 session_id 关联可查

## Dependencies

- PHASE-004（工单派发需要用户身份）
- PHASE-005（真实故障触发工单，伪传感器场景可选支持）

## Notes

移动端形态（响应式 Web vs 原生 App）需产品评审确定。若现场已有 EAM 系统，优先考虑 API 集成而非自建工单模块。
