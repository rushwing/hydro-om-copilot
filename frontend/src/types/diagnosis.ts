// ── Enums ────────────────────────────────────────────────────────────────────

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type DiagnosisTopic = "vibration_swing" | "governor_oil" | "bearing_temp";

// ── Structured output models (mirrors backend Pydantic) ──────────────────────

export interface RootCause {
  rank: number;
  title: string;
  probability: number;
  evidence: string[];
  parameters_to_confirm: string[];
}

export interface CheckStep {
  step: number;
  action: string;
  expected?: string;
  caution?: string;
}

export interface DiagnosisResult {
  session_id: string;
  unit_id?: string;
  topic?: DiagnosisTopic;
  root_causes: RootCause[];
  check_steps: CheckStep[];
  risk_level: RiskLevel;
  escalation_required: boolean;
  escalation_reason?: string;
  report_draft?: string;
  sources: string[];
}

// ── SSE event payloads ───────────────────────────────────────────────────────

export interface SSEStatusPayload {
  node: string;
  phase: "start" | "end";
}

export interface SSETokenPayload {
  text: string;
}

export interface SSEErrorPayload {
  message: string;
}

export type SSEEvent =
  | { event: "status"; data: SSEStatusPayload }
  | { event: "token"; data: SSETokenPayload }
  | { event: "result"; data: DiagnosisResult }
  | { event: "error"; data: SSEErrorPayload };

// ── Request ──────────────────────────────────────────────────────────────────

export interface DiagnosisRequest {
  session_id?: string;
  unit_id?: string;
  query: string;
  image_base64?: string;
}
