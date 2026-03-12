"""
symptom_parser node — converts free-text operator input into a structured ParsedSymptom.
"""

import traceback

from app.agents.state import AgentState, ParsedSymptom
from app.utils.anthropic_client import llm_json
from app.utils.prompts import SYMPTOM_PARSER_PROMPT

TOPIC_KEYWORDS = {
    "vibration_swing":       ["振动", "摆度", "抖动", "晃动", "位移", "瓦振", "轴振"],
    "governor_oil_pressure": ["调速器", "油压", "压油罐", "主配压阀", "导叶", "开度", "漏油"],
    "bearing_temp_cooling":  ["轴承", "温度", "温升", "冷却水", "推力", "导轴承", "过热"],
}


def _infer_topic(parsed: ParsedSymptom) -> str:
    text = " ".join(parsed.get("symptoms", []) + [parsed.get("device", "")])
    scores = {topic: 0 for topic in TOPIC_KEYWORDS}
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[topic] += 1
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] > 0 else "vibration_swing"


async def symptom_parser_node(state: AgentState) -> dict:
    session_id = state.get("session_id", "")
    prompt = SYMPTOM_PARSER_PROMPT.format(query=state["raw_query"])
    try:
        result: ParsedSymptom = await llm_json(
            prompt, max_tokens=512, _session_id=session_id, _node="symptom_parser"
        )
    except Exception as exc:
        print(f"[symptom_parser ERROR] {exc}\n{traceback.format_exc()}", flush=True)
        return {"error": f"symptom_parser failed: {exc}", "parsed_symptom": None, "topic": None}

    topic = _infer_topic(result)
    return {"parsed_symptom": result, "topic": topic}
