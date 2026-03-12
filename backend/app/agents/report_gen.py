"""
report_gen node — generates check-step SOP and a ready-to-use shift handover draft.
"""

import json
import traceback

from app.agents.state import AgentState
from app.utils.anthropic_client import llm_json
from app.utils.prompts import REPORT_GEN_PROMPT


async def report_gen_node(state: AgentState) -> dict:
    prompt = REPORT_GEN_PROMPT.format(
        query=state["raw_query"],
        unit_id=(state.get("parsed_symptom") or {}).get("unit_id", "未知机组"),
        root_causes=json.dumps(state.get("root_causes", []), ensure_ascii=False),
        risk_level=state.get("risk_level", "medium"),
        escalation_required=state.get("escalation_required", False),
        escalation_reason=state.get("escalation_reason") or "",
    )

    session_id = state.get("session_id", "")
    try:
        result = await llm_json(
            prompt, max_tokens=8192, _session_id=session_id, _node="report_gen"
        )
    except Exception as exc:
        print(f"[report_gen_node ERROR] {exc}\n{traceback.format_exc()}", flush=True)
        return {
            "check_steps": [],
            "report_draft": None,
            "error": f"report_gen failed: {exc}",
        }

    return {
        "check_steps": result.get("check_steps", []),
        "report_draft": result.get("report_draft"),
    }
