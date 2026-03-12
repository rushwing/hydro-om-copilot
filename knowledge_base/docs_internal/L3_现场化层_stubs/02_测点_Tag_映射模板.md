---
doc_id: L3.SITE.002
doc_level: L3
knowledge_type: tag_mapping_stub
route_keys:
  - historian_tag
  - scada_tag
  - monitor_tag
upstream_docs:
  - L2.TOPIC.VIB.001
  - L2.TOPIC.GOV.001
  - L2.TOPIC.BEAR.001
---

# 测点 Tag 映射模板

## 字段模板

| 参数名称 | 示例值 | 字段说明 |
| --- | --- | --- |
| 电站名称 |  |  |
| 机组号 |  |  |
| tag_code |  | 实际系统 TAG（唯一标识） |
| 中文名称 |  | 如：上导X向振动 |
| 英文别名 |  | 可选，用于与历史库对齐 |
| 专业域 |  | 振动 / 摆度 / 温度 / 油压 / 水压脉动等 |
| 设备对象 |  | 上导 / 水导 / 调速器 / 冷却器等 |
| 测点位置 |  | X/Y向、瓦号、管段等 |
| 单位 |  | μm / mm·s⁻¹ / ℃ / MPa |
| 采样周期 |  | 单位：秒，如 1s / 5s |
| 数据来源系统 |  | SCADA / PLC / 振摆监测 / DCS |
| 质量标识 |  | 正常 / 检修退出 / 异常漂移 |

## 接入要求

- 同一物理量允许多个系统别名，但要指定主 TAG。
- 关键测点建议标记是否参与保护、联锁、告警。
- 后续 RAG 检索时，TAG 可作为实体识别和参数补齐依据。
