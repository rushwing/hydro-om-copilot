"""
reasoning node — produces Top-3 root causes with evidence chains.
"""

import json
import traceback

from app.agents.state import AgentState
from app.utils.anthropic_client import llm_json
from app.utils.prompts import REASONING_PROMPT


def _format_docs(docs: list[dict]) -> str:
    return "\n\n---\n\n".join(
        f"[{d.get('doc_id', '?')}] {d.get('content', '')}" for d in docs[:5]
    )


async def reasoning_node(state: AgentState) -> dict:
    retrieved = state.get("retrieved") or {}
    prompt = REASONING_PROMPT.format(
        query=state["raw_query"],
        parsed_symptom=json.dumps(state.get("parsed_symptom") or {}, ensure_ascii=False),
        topic=state.get("topic", ""),
        procedure_context=_format_docs(retrieved.get("procedure_docs", [])),
        rule_context=_format_docs(retrieved.get("rule_docs", [])),
        case_context=_format_docs(retrieved.get("case_docs", [])),
        ocr_text=state.get("ocr_text") or "",
    )

    session_id = state.get("session_id", "")
    try:
        result = await llm_json(
            prompt, max_tokens=4096, _session_id=session_id, _node="reasoning"
        )
    except Exception as exc:
        print(f"[reasoning_node ERROR] {exc}\n{traceback.format_exc()}", flush=True)
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
