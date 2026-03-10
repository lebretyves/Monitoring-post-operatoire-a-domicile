import type { AlertRecord, NotificationRecord } from "../types/alerts";
import type {
  ClinicalPackageResponse,
  ClinicalContextSelection,
  MlFeedbackPayload,
  MlPredictionResponse,
  PatientSummary,
  PrioritizationResponse,
  QuestionnaireSelectionResponse,
  TerrainGuidanceRequest,
  TerrainGuidanceResponse,
  TrendResponse,
  VitalPayload
} from "../types/vitals";

const API_BASE = import.meta.env?.VITE_API_BASE_URL ?? "http://localhost:8000";

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

export function getPatient(patientId: string): Promise<PatientSummary> {
  return readJson<PatientSummary>(`/api/patients/${patientId}`);
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

export function getNotifications(
  patientId?: string,
  status?: "UNREAD" | "READ"
): Promise<NotificationRecord[]> {
  const params = new URLSearchParams();
  if (patientId) {
    params.set("patient_id", patientId);
  }
  if (status) {
    params.set("status", status);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return readJson<NotificationRecord[]>(`/api/notifications${suffix}`);
}

export function getPushConfig(): Promise<{ enabled: boolean; public_key: string }> {
  return readJson<{ enabled: boolean; public_key: string }>("/api/push/config");
}

export function registerPushSubscription(payload: {
  user_id: string;
  device_id: string;
  user_agent?: string;
  subscription: {
    endpoint: string;
    keys: {
      p256dh: string;
      auth: string;
    };
  };
}): Promise<{ status: string }> {
  return fetch(`${API_BASE}/api/push/subscriptions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on push subscribe`);
    }
    return response.json() as Promise<{ status: string }>;
  });
}

export function unregisterPushSubscription(endpoint: string): Promise<{ status: string }> {
  return fetch(`${API_BASE}/api/push/subscriptions`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ endpoint })
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on push unsubscribe`);
    }
    return response.json() as Promise<{ status: string }>;
  });
}

export function markNotificationRead(notificationId: number): Promise<NotificationRecord> {
  return fetch(`${API_BASE}/api/notifications/${notificationId}/read?user=demo`, { method: "POST" }).then(
    async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} on notification read`);
      }
      return response.json() as Promise<NotificationRecord>;
    }
  );
}

export function getClinicalPackage(patientId: string): Promise<ClinicalPackageResponse> {
  return readJson<ClinicalPackageResponse>(`/api/llm/${patientId}/clinical-package`);
}

export function getDifferentialQuestionnaire(patientId: string): Promise<QuestionnaireSelectionResponse> {
  return readJson<QuestionnaireSelectionResponse>(`/api/llm/${patientId}/questionnaire`);
}

export function analyzeClinicalPackage(
  patientId: string,
  clinicalContext: ClinicalContextSelection
): Promise<ClinicalPackageResponse> {
  return fetch(`${API_BASE}/api/llm/${patientId}/clinical-package`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(clinicalContext)
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on clinical package analysis`);
    }
    return response.json() as Promise<ClinicalPackageResponse>;
  });
}

export function getPrioritizedPatients(): Promise<PrioritizationResponse> {
  return readJson<PrioritizationResponse>("/api/llm/prioritize/patients");
}

export function generateTerrainGuidance(
  patientId: string,
  payload: TerrainGuidanceRequest
): Promise<TerrainGuidanceResponse> {
  return fetch(`${API_BASE}/api/llm/${patientId}/terrain-guidance`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  }).then(async (response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: `HTTP ${response.status} on terrain guidance` }));
      throw new Error(err.detail ?? `HTTP ${response.status} on terrain guidance`);
    }
    return response.json() as Promise<TerrainGuidanceResponse>;
  });
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
