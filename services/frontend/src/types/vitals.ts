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

export interface MlFeedbackRecord {
  id: number;
  patient_id: string;
  alert_id?: number | null;
  label: string;
  comment: string;
  pathology?: string | null;
  surgery_type?: string | null;
  has_critical?: number | null;
  created_at: string;
}

export interface MlPredictionResponse {
  patient_id: string;
  patient_name: string;
  pathology: string;
  probability: number | null;
  model_ready: boolean;
  sample: Record<string, string | number | null>;
  last_vitals: VitalPayload;
  recent_feedback: MlFeedbackRecord[];
}

export interface MlFeedbackPayload {
  decision: "validate" | "invalidate";
  target?: "critical" | "non_critical";
  pathology?: string;
  alert_id?: number;
  comment?: string;
}
