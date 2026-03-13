---
phase_id: phase-2
title: 自动传感监测与诊断
status: done
priority: P1
---

## Goal

后台自动轮询伪传感器，检测故障后自动触发诊断，结果推送至前端无需人工介入。

## In Scope

- 三个 FastMCP 伪传感器 Server：振动摆度 / 调速器油压 / 轴承温升
- FaultAggregator 跨传感器故障聚合与冷却期管理
- AutoDiagnosisService：队列 + 后台 worker
- GET /diagnosis/auto-results API
- AutoDiagnosisPanel 前端：Epoch 阶段条 / 队列展示 / 结果归档

## Out of Scope

- 真实 PLC/SCADA 接入（属 PHASE-005）
- 鉴权（属 PHASE-004）
- 工单派发（属 PHASE-007）

## Exit Criteria

- 设置 AUTO_RANDOM_PROBLEMS_GEN=true 后，系统自动触发完整诊断链
- 前端 AutoDiagnosisPanel 展示自动诊断结果
- 同一机组在冷却期（DIAGNOSIS_COOLDOWN）内不重复触发诊断

## Dependencies

- PHASE-001（需要诊断 pipeline 已就绪）

## Notes

已合并至 main 分支。伪随机引擎（pseudo_random.py）与门限常量（thresholds.py）已实现，三个 MCP Server 可独立启动。
