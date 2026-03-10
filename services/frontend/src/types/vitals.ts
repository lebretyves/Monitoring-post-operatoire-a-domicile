export interface VitalPayload {
  ts: string;
  patient_id: string;
  profile: string;
  scenario: string;
  scenario_label?: string;
  hr: number;
  spo2: number;
  sbp: number;
  dbp: number;
  map: number;
  rr: number;
  temp: number;
  room: string;
  battery: number;
  postop_day: number;
  surgery_type: string;
  shock_index?: number;
}

export interface PatientSummary {
  id: string;
  full_name: string;
  profile: string;
  surgery_type: string;
  postop_day: number;
  risk_level: string;
  room: string;
  history: string[];
  last_vitals?: VitalPayload | null;
}

export interface TrendPoint {
  ts: string;
  values: Record<string, number>;
}

export interface TrendResponse {
  patient_id: string;
  metric: string;
  hours: number;
  points: TrendPoint[];
  anomaly: {
    enabled: boolean;
    status: string;
    is_anomaly?: boolean;
  };
}

export interface ClinicalContextSelection {
  patient_factors: string[];
  perioperative_context: string[];
  free_text: string;
  questionnaire?: QuestionnaireSubmission;
}

export interface QuestionnaireOption {
  value: string;
  label: string;
}

export interface QuestionnaireQuestion {
  id: string;
  label: string;
  type: string;
  options: QuestionnaireOption[];
}

export interface QuestionnaireModule {
  id: string;
  title: string;
  description: string;
  targets: string[];
  matched_triggers: string[];
  source_refs: Array<{ label: string; url: string }>;
  questions: QuestionnaireQuestion[];
}

export interface QuestionnaireSelectionResponse {
  patient_id: string;
  trigger_summary: string[];
  modules: QuestionnaireModule[];
}

export interface QuestionnaireAnswer {
  module_id: string;
  question_id: string;
  answer: string;
}

export interface QuestionnaireSubmission {
  responder: string;
  comment: string;
  answers: QuestionnaireAnswer[];
}

export interface ClinicalHypothesisRow {
  label: string;
  compatibility: "high" | "medium" | "low";
  compatibility_percent: number;
  arguments_for: string[];
  arguments_against: string[];
}

export interface ExplanatoryScore {
  score: number;
  level: "low" | "medium" | "high" | "critical";
  reasons: string[];
}

export interface AnalysisStateSnapshot {
  mode: "active" | "resting" | "stale";
  cache_status: "fresh" | "cached" | "stale";
  generated_at?: string | null;
  submitted_at?: string | null;
  delta_signals: string[];
  trigger_reason?: string;
  anchor_vitals?: {
    ts?: string;
    hr: number;
    spo2: number;
    map: number;
    rr: number;
    temp: number;
    shock_index?: number;
  } | null;
}

export interface ClinicalPackageResponse {
  source: "ollama" | "rule-based";
  llm_status?: "ollama" | "rule-based" | "llm-unavailable" | "disabled";
  patient_id: string;
  summary_text: string;
  explanatory_score: ExplanatoryScore;
  analysis_state: AnalysisStateSnapshot;
  questionnaire_state?: QuestionnaireSubmission | null;
  questionnaire_baseline_hypothesis_ranking?: ClinicalHypothesisRow[] | null;
  structured_synthesis: string;
  alert_explanations: string[];
  hypothesis_ranking: ClinicalHypothesisRow[];
  trajectory_status: "stable" | "worsening" | "switching" | "recovering";
  trajectory_explanation: string;
  recheck_recommendations: string[];
  handoff_summary: string;
  scenario_consistency: string;
}

export interface PatientPrioritizationRow {
  patient_id: string;
  priority_rank: number;
  priority_level: "high" | "medium" | "low";
  reason: string;
}

export interface PrioritizationResponse {
  source: "ollama" | "rule-based";
  llm_status?: "ollama" | "rule-based" | "llm-unavailable" | "disabled";
  prioritized_patients: PatientPrioritizationRow[];
}

export interface MlFeedbackRecord {
  id: number;
  patient_id: string;
  alert_id?: number | null;
  label: string;
  comment: string;
  pathology?: string | null;
  diagnosis_decision?: "validated" | "rejected" | null;
  final_diagnosis?: string | null;
  surgery_type?: string | null;
  has_critical?: number | null;
  created_at: string;
}

export interface MlRiskScore {
  score: number;
  level: string;
  reference: string;
  active_threshold_count?: number;
  triggered_thresholds?: string[];
  signal_count?: number;
  signals?: string[];
  course_hours?: number;
}

export interface MlPredictionResponse {
  patient_id: string;
  patient_name: string;
  pathology: string;
  probability: number | null;
  ml_probability?: number | null;
  model_ready: boolean;
  sample: Record<string, string | number | null>;
  last_vitals: VitalPayload;
  immediate_criticality: MlRiskScore;
  evolving_risk: MlRiskScore;
  recent_feedback: MlFeedbackRecord[];
}

export interface MlFeedbackPayload {
  decision: "validate" | "invalidate";
  target?: "critical" | "non_critical";
  pathology?: string;
  diagnosis_decision?: "validated" | "rejected";
  final_diagnosis?: string;
  alert_id?: number;
  comment?: string;
}

export interface TerrainGuidanceRequest {
  patient_factors: string[];
  perioperative_context: string[];
  free_text: string;
  questionnaire?: QuestionnaireSubmission | null;
}

export interface TerrainGuidanceResponse {
  source: "ollama" | "rule-based";
  llm_status: "ollama" | "rule-based" | "llm-unavailable" | "disabled";
  patient_id: string;
  diagnosis_decision: "validated" | "rejected";
  diagnosis_final: string;
  personalization_level: "low" | "medium" | "high";
  warning: string;
  immediate_actions: string[];
  surveillance_points: string[];
  escalation_triggers: string[];
  transmission_summary: string;
  cited_sources: string[];
}
