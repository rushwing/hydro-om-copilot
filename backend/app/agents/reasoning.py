"""
reasoning node — produces Top-3 root causes with evidence chains.
Streams tokens back through state for SSE delivery.
"""

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import AgentState
from app.config import settings
from app.utils.prompts import REASONING_PROMPT

_llm = ChatAnthropic(
    model=settings.llm_model,
    temperature=settings.llm_temperature,
    api_key=settings.anthropic_api_key,
)

_chain = (
    ChatPromptTemplate.from_template(REASONING_PROMPT)
    | _llm
    | JsonOutputParser()
)


def _format_docs(docs: list[dict]) -> str:
    return "\n\n---\n\n".join(
        f"[{d.get('doc_id', '?')}] {d.get('content', '')}" for d in docs[:5]
    )


async def reasoning_node(state: AgentState) -> dict:
    retrieved = state.get("retrieved") or {}
    procedure_ctx = _format_docs(retrieved.get("procedure_docs", []))
    rule_ctx = _format_docs(retrieved.get("rule_docs", []))
    case_ctx = _format_docs(retrieved.get("case_docs", []))

    try:
        result = await _chain.ainvoke(
            {
                "query": state["raw_query"],
                "parsed_symptom": json.dumps(state.get("parsed_symptom") or {}, ensure_ascii=False),
                "topic": state.get("topic", ""),
                "procedure_context": procedure_ctx,
                "rule_context": rule_ctx,
                "case_context": case_ctx,
                "ocr_text": state.get("ocr_text") or "",
            }
        )
    except Exception as exc:
        return {
            "root_causes": [],
            "risk_level": "medium",
            "escalation_required": False,
            "escalation_reason": None,
            "error": f"reasoning failed: {exc}",
        }

    return {
        "root_causes": result.get("root_causes", []),
        "risk_level": result.get("risk_level", "medium"),
        "escalation_required": result.get("escalation_required", False),
        "escalation_reason": result.get("escalation_reason"),
    }
