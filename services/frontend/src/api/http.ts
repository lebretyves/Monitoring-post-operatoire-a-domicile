import type { AlertRecord } from "../types/alerts";
import type { MlFeedbackPayload, MlPredictionResponse, PatientSummary, TrendResponse, VitalPayload } from "../types/vitals";

const API_BASE = ((import.meta as any).env?.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

async function readJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} on ${path}`);
  }
  return response.json() as Promise<T>;
}

export function getPatients(): Promise<PatientSummary[]> {
  return readJson<PatientSummary[]>("/api/patients");
}

export function refreshPatients(): Promise<{
  status: string;
  mode: string;
  rule: string;
  assignments: Array<{
    patient_id: string;
    case_id: string;
    case_label: string;
    scenario: string;
    scenario_label: string;
    profile: string;
    origin: string;
    full_name: string;
    surgery_type: string;
    postop_day: number;
  }>;
}> {
  return fetch(`${API_BASE}/api/patients/refresh`, { method: "POST" }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on patient refresh`);
    }
    return response.json();
  });
}

export function getLastVitals(patientId: string): Promise<VitalPayload> {
  return readJson<VitalPayload>(`/api/patients/${patientId}/last-vitals`);
}

export function getHistory(patientId: string, hours = 24): Promise<TrendResponse> {
  return readJson<TrendResponse>(`/api/trends/${patientId}?metric=all&hours=${hours}`);
}

export function getAlerts(patientId?: string, pathology?: string, surgeryType?: string): Promise<AlertRecord[]> {
  const params = new URLSearchParams();
  if (patientId) {
    params.set("patient_id", patientId);
  }
  if (pathology) {
    params.set("pathology", pathology);
  }
  if (surgeryType) {
    params.set("surgery_type", surgeryType);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return readJson<AlertRecord[]>(`/api/alerts${suffix}`);
}

export function ackAlert(alertId: number): Promise<AlertRecord> {
  return fetch(`${API_BASE}/api/alerts/${alertId}/ack?user=demo`, { method: "POST" }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on alert ack`);
    }
    return response.json() as Promise<AlertRecord>;
  });
}

export function getSummary(patientId: string): Promise<{ patient_id: string; source: string; summary: string }> {
  return readJson(`/api/summaries/${patientId}`);
}

export function getMlPrediction(patientId: string): Promise<MlPredictionResponse> {
  return readJson<MlPredictionResponse>(`/api/ml/${patientId}/predict`);
}

export function submitMlFeedback(
  patientId: string,
  payload: MlFeedbackPayload
): Promise<{ status: string; patient_id: string; pathology: string; has_critical: number; feedback: any }> {
  return fetch(`${API_BASE}/api/ml/${patientId}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on ML feedback`);
    }
    return response.json();
  });
}

export function trainMlModel(): Promise<{ status: string; accuracy: number | null; rows: number; mode: string }> {
  return fetch(`${API_BASE}/api/ml/train`, { method: "POST" }).then(async (response) => {
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: "ML train failed" }));
      throw new Error(payload.detail ?? `HTTP ${response.status} on ML train`);
    }
    return response.json();
  });
}

export function exportCsvUrl(patientId: string): string {
  return `${API_BASE}/api/export/${patientId}/csv`;
}

export function exportPdfUrl(patientId: string): string {
  return `${API_BASE}/api/export/${patientId}/pdf`;
}
