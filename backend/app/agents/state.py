import operator
from typing import Annotated, TypedDict


class ParsedSymptom(TypedDict, total=False):
    """Structured output from symptom_parser node."""

    unit_id: str | None
    device: str | None        # e.g. 导叶, 推力轴承, 主配压阀
    symptoms: list[str]          # free-text symptom phrases
    alarms: list[str]            # alarm codes / names mentioned
    duration: str | None      # how long the symptom has persisted
    operating_mode: str | None  # e.g. 满载, 空载, 启机


class RetrievedContext(TypedDict, total=False):
    procedure_docs: list[dict]   # L2 specialist guides + L1 overview chunks
    rule_docs: list[dict]        # L2.SUPPORT.RULE.001 threshold chunks
    case_docs: list[dict]        # L2.SUPPORT.CASE.001 similar-case chunks


class AgentState(TypedDict):
    """Shared state across all LangGraph nodes."""

    # ── Input ──────────────────────────────────────────────────────────────
    session_id: str
    raw_query: str
    image_base64: str | None

    # ── Parsed ─────────────────────────────────────────────────────────────
    parsed_symptom: ParsedSymptom | None
    ocr_text: str | None          # extracted from image_agent

    # ── Routing ────────────────────────────────────────────────────────────
    topic: str | None             # vibration_swing | governor_oil_pressure | bearing_temp_cooling

    # ── Retrieval ──────────────────────────────────────────────────────────
    retrieved: RetrievedContext | None

    # ── Reasoning output ───────────────────────────────────────────────────
    root_causes: list[dict]          # list of RootCause-shaped dicts
    check_steps: list[dict]          # list of CheckStep-shaped dicts
    risk_level: str                  # low | medium | high | critical
    escalation_required: bool
    escalation_reason: str | None
    report_draft: str | None

    # ── Streaming ──────────────────────────────────────────────────────────
    # Accumulates LLM token chunks for SSE streaming
    stream_tokens: Annotated[list[str], operator.add]

    # ── Metadata ───────────────────────────────────────────────────────────
    sources: list[str]               # doc_ids referenced
    error: str | None
