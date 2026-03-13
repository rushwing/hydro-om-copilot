---
phase_id: phase-5
title: 机组/监控在线状态实时同步
status: draft
priority: P2
---

## Goal

接入真实 PLC/SCADA 数据源，替换伪随机传感器，实现生产环境真实监测。

## In Scope

- 真实传感器适配层（替换 pseudo_random.py）
- PLC/SCADA 数据协议对接（Modbus / OPC-UA / MQTT，视现场确定）
- 机组在线/离线状态实时展示（前端状态面板）
- 传感器数据有效性校验与异常值过滤
- 历史趋势数据存储（时序 DB 选型 TBD）

## Out of Scope

- 传感器硬件安装与现场调试（属工程实施范畴）
- 多租户数据隔离（属 PHASE-006）

## Exit Criteria

- 生产环境传感器数据替换伪随机引擎后，自动诊断链路正常触发
- 机组在线状态变更在前端 3 秒内更新
- 数据中断时系统优雅降级（告警而非崩溃）

## Dependencies

- PHASE-002（自动诊断基础架构已就绪）
- PHASE-004（生产接入需鉴权）

## Notes

具体协议由现场环境决定，需提前调研水电厂 SCADA 系统型号。时序数据库选型待确定（候选：InfluxDB / TimescaleDB）。
