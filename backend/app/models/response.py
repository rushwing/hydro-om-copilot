from enum import StrEnum

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiagnosisTopic(StrEnum):
    VIBRATION_SWING = "vibration_swing"
    GOVERNOR_OIL_PRESSURE = "governor_oil_pressure"
    BEARING_TEMP_COOLING = "bearing_temp_cooling"


class RootCause(BaseModel):
    """A single root-cause hypothesis with supporting evidence."""

    rank: int = Field(description="Ranking (1 = most likely)")
    title: str = Field(description="Short root-cause label, e.g. '导叶开度不一致'")
    probability: float = Field(description="Estimated probability [0, 1]", ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence items")
    parameters_to_confirm: list[str] = Field(
        default_factory=list,
        description="Additional parameters operator should check",
    )


class CheckStep(BaseModel):
    """A single step in the inspection SOP."""

    step: int
    action: str
    expected: str | None = None
    caution: str | None = None


class DiagnosisResult(BaseModel):
    """Final structured diagnosis output."""

    session_id: str
    unit_id: str | None = None
    topic: DiagnosisTopic | None = Field(default=None)
    root_causes: list[RootCause] = Field(default_factory=list)
    check_steps: list[CheckStep] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    escalation_required: bool = False
    escalation_reason: str | None = None
    report_draft: str | None = Field(
        default=None,
        description="Ready-to-use defect report / shift handover draft",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Knowledge base document IDs used for this diagnosis",
    )


class SSEEvent(BaseModel):
    """Streaming event sent over SSE."""

    event: str = Field(description="Event type: token | status | result | error")
    data: str = Field(description="Payload; JSON string for structured events")
