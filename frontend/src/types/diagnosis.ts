// ── Enums ────────────────────────────────────────────────────────────────────

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type DiagnosisTopic = "vibration_swing" | "governor_oil_pressure" | "bearing_temp_cooling";

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

// ── Auto-diagnosis types ──────────────────────────────────────────────────────

export interface SensorPointSnapshot {
  tag: string;
  name_cn: string;
  value: number;
  alarm_state: "normal" | "warn" | "alarm" | "trip";
  trend: "stable" | "rising" | "falling";
  thresholds: { unit: string; [key: string]: unknown };
}

export interface PendingFaultItem {
  unit_id: string;
  fault_types: string[];
  symptom_preview: string;
  queued_at: string;
}

export interface CurrentDiagnosisInfo {
  session_id: string;
  unit_id: string;
  fault_types: string[];
  phase: string;
  stream_preview: string;
  sensor_data: SensorPointSnapshot[];
  started_at: string;
}

export type EpochPhase = "NORMAL" | "PRE_FAULT" | "FAULT" | "COOL_DOWN";

export interface AutoDiagnosisStatus {
  running: boolean;
  is_simulated: boolean;
  current: CurrentDiagnosisInfo | null;
  pending_queue: PendingFaultItem[];
  completed_count: number;
  unit_cooldowns: Record<string, number>;
  epoch_num: number;
  epoch_elapsed_s: number;
  epoch_phase: EpochPhase;
}

export interface AutoDiagnosisRecord {
  session_id: string;
  unit_id: string;
  fault_types: string[];
  symptom_text: string;
  triggered_at: string;
  risk_level: RiskLevel | null;
  escalation_required: boolean;
  escalation_reason: string | null;
  root_causes: RootCause[];
  check_steps: CheckStep[];
  report_draft: string | null;
  sources: string[];
  error: string | null;
}
