"""
report_gen node — generates check-step SOP and a ready-to-use shift handover draft.
"""

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import AgentState
from app.config import settings
from app.utils.prompts import REPORT_GEN_PROMPT

_llm = ChatAnthropic(
    model=settings.llm_model,
    temperature=settings.llm_temperature,
    api_key=settings.anthropic_api_key,
)

_chain = (
    ChatPromptTemplate.from_template(REPORT_GEN_PROMPT)
    | _llm
    | JsonOutputParser()
)


async def report_gen_node(state: AgentState) -> dict:
    try:
        result = await _chain.ainvoke(
            {
                "query": state["raw_query"],
                "unit_id": state.get("parsed_symptom", {}).get("unit_id", "未知机组"),
                "root_causes": json.dumps(state.get("root_causes", []), ensure_ascii=False),
                "risk_level": state.get("risk_level", "medium"),
                "escalation_required": state.get("escalation_required", False),
                "escalation_reason": state.get("escalation_reason", ""),
            }
        )
    except Exception as exc:
        return {
            "check_steps": [],
            "report_draft": None,
            "error": f"report_gen failed: {exc}",
        }

    return {
        "check_steps": result.get("check_steps", []),
        "report_draft": result.get("report_draft"),
    }
