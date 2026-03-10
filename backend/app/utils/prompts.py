"""
Prompt templates for all LangGraph nodes.
All prompts are in Chinese to match the domain.
"""

SYMPTOM_PARSER_PROMPT = """\
你是一名水电站运维专家助手。请从以下运维人员描述中，提取结构化症状信息，以 JSON 格式返回。

## 描述
{query}

## 输出格式（JSON）
{{
  "unit_id": "机组编号（如 #1机），若未提及则为 null",
  "device": "受影响设备名称（如 导叶、推力轴承、主配压阀）",
  "symptoms": ["症状1", "症状2"],
  "alarms": ["报警名称或代码"],
  "duration": "持续时间（如 约2小时、上次开机起），若未提及则为 null",
  "operating_mode": "运行工况（如 满载、空载、启机过程），若未提及则为 null"
}}

只返回 JSON，不要其他文字。
"""

REASONING_PROMPT = """\
你是一名资深水电机组故障诊断专家。请根据以下信息，给出 Top-3 根因假设及检查建议。

## 运维人员描述
{query}

## 解析出的症状
{parsed_symptom}

## 故障类型
{topic}

## 规程参考（L2专题指南 + L1总览）
{procedure_context}

## 规则库（硬阈值 / 操作红线）
{rule_context}

## 案例库（历史相似案例）
{case_context}

## 截图OCR文本（如有）
{ocr_text}

## 输出格式（JSON）
{{
  "root_causes": [
    {{
      "rank": 1,
      "title": "根因标题",
      "probability": 0.6,
      "evidence": ["证据1", "证据2"],
      "parameters_to_confirm": ["需要进一步确认的参数1"]
    }}
  ],
  "risk_level": "low|medium|high|critical",
  "escalation_required": false,
  "escalation_reason": null
}}

严格按 JSON 输出，不要其他文字。风险等级判断依据规则库中的超限阈值与操作红线。
"""

REPORT_GEN_PROMPT = """\
你是一名水电站运维专家助手。请根据以下诊断结论，生成：
1. 结构化检查步骤（SOP）
2. 班组交班汇报草稿（可直接复制使用）

## 原始描述
{query}

## 机组编号
{unit_id}

## Top-3 根因
{root_causes}

## 风险等级
{risk_level}

## 是否需要升级处理
{escalation_required}（原因：{escalation_reason}）

## 输出格式（JSON）
{{
  "check_steps": [
    {{
      "step": 1,
      "action": "检查导叶开度反馈信号是否一致",
      "expected": "各导叶开度差值 < 3%",
      "caution": "操作前确认调速器在手动模式"
    }}
  ],
  "report_draft": "运维汇报草稿全文（纯文本，含时间、机组、现象、初步判断、已采取措施）"
}}

严格按 JSON 输出，不要其他文字。检查步骤按优先级排序，危险操作务必加 caution 提示。
"""
