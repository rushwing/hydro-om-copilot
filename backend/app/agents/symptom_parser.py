"""
symptom_parser node — converts free-text operator input into a structured ParsedSymptom.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import AgentState, ParsedSymptom
from app.config import settings
from app.utils.prompts import SYMPTOM_PARSER_PROMPT

_llm = ChatAnthropic(
    model=settings.llm_model,
    temperature=settings.llm_temperature,
    api_key=settings.anthropic_api_key,
)

_chain = (
    ChatPromptTemplate.from_template(SYMPTOM_PARSER_PROMPT)
    | _llm
    | JsonOutputParser()
)

TOPIC_KEYWORDS = {
    "vibration_swing":      ["振动", "摆度", "抖动", "晃动", "位移", "瓦振", "轴振"],
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
    try:
        result: ParsedSymptom = await _chain.ainvoke({"query": state["raw_query"]})
    except Exception as exc:
        return {"error": f"symptom_parser failed: {exc}", "parsed_symptom": None, "topic": None}

    topic = _infer_topic(result)
    return {
        "parsed_symptom": result,
        "topic": topic,
    }
