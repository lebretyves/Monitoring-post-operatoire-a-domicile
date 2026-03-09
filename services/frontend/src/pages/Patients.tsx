import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ackAlert, getAlerts, getPatients, getPrioritizedPatients, refreshPatients } from "../api/http";
import { connectLiveSocket } from "../api/ws";
import { AlertsPanel } from "../components/AlertsPanel";
import {
  ALARM_STORAGE_KEY,
  PatientMonitorStrip,
  type PatientAlarmLimits,
  type PatientMonitorLayout,
  loadStoredAlarmLimits,
} from "../components/PatientMonitorStrip";
import type { AlertRecord, LiveEvent } from "../types/alerts";
import type { PatientPrioritizationRow, PatientSummary } from "../types/vitals";

export function PatientsPage() {
  const MAX_ALERTS = 48;
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [prioritizedPatients, setPrioritizedPatients] = useState<PatientPrioritizationRow[]>([]);
  const [prioritizationSource, setPrioritizationSource] = useState("indisponible");
  const [prioritizationStatus, setPrioritizationStatus] = useState("indisponible");
  const [wsStatus, setWsStatus] = useState("connecting");
  const [refreshing, setRefreshing] = useState(false);
  const [prioritizing, setPrioritizing] = useState(false);
  const [alarmLimits, setAlarmLimits] = useState<Record<string, PatientAlarmLimits>>(() => loadStoredAlarmLimits());
  const [viewMode, setViewMode] = useState<PatientMonitorLayout>("full");
  const prioritizationByPatient = new Map(prioritizedPatients.map((row) => [row.patient_id, row]));
  const prioritizationLabel = formatPrioritizationSource(prioritizationStatus, prioritizationSource);
  const recentAlertCount = alerts.length;

  useEffect(() => {
    window.localStorage.setItem(ALARM_STORAGE_KEY, JSON.stringify(alarmLimits));
  }, [alarmLimits]);

  async function loadDashboard() {
    const [patientRows, alertRows] = await Promise.all([getPatients(), getAlerts()]);
    setPatients(patientRows);
    setAlerts(alertRows.slice(0, MAX_ALERTS));
  }

  async function refreshPrioritization() {
    setPrioritizing(true);
    try {
      const prioritization = await getPrioritizedPatients();
      setPrioritizedPatients(prioritization.prioritized_patients);
      setPrioritizationSource(prioritization.source);
      setPrioritizationStatus(prioritization.llm_status ?? prioritization.source);
    } catch (error) {
      console.error(error);
      setPrioritizedPatients([]);
      setPrioritizationSource("indisponible");
      setPrioritizationStatus("indisponible");
    } finally {
      setPrioritizing(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      await loadDashboard();
    };
    load().catch(console.error);
    const cleanup = connectLiveSocket((event: LiveEvent) => {
      if (event.type === "vitals") {
        setPatients((current) =>
          current.map((patient) =>
            patient.id === event.patient_id ? { ...patient, last_vitals: event.payload } : patient
          )
        );
      }
      if (event.type === "alert") {
        setAlerts((current) => [event.payload as AlertRecord, ...current].slice(0, MAX_ALERTS));
      }
      if (event.type === "ack") {
        setAlerts((current) =>
          current.map((alert) => (alert.id === event.payload.id ? (event.payload as AlertRecord) : alert))
        );
      }
    }, setWsStatus);
    return () => {
      mounted = false;
      cleanup();
    };
  }, []);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <section
        style={{
          padding: 24,
          borderRadius: 30,
          background:
            "linear-gradient(180deg, rgba(5, 17, 30, 0.96), rgba(8, 31, 52, 0.96))",
          color: "#f8fafc",
          boxShadow: "0 20px 38px rgba(2, 12, 27, 0.28)",
          border: "1px solid rgba(125, 164, 203, 0.16)",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 18,
            alignItems: "stretch",
          }}
        >
          <div style={{ display: "grid", gap: 16, flex: "1 1 580px", maxWidth: 700 }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                width: "fit-content",
                padding: "6px 10px",
                borderRadius: 999,
                background: "rgba(94, 211, 255, 0.09)",
                color: "#bfe9ff",
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: 1,
                textTransform: "uppercase",
              }}
            >
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 999,
                  background: "#38bdf8",
                  boxShadow: "0 0 14px rgba(56, 189, 248, 0.72)",
                }}
              />
              Monitoring
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              <h1 style={{ margin: 0, fontSize: 34, lineHeight: 1.05 }}>Monitoring post-operatoire a domicile</h1>
              <div style={{ color: "#9fb6cb", fontSize: 14, maxWidth: 760 }}>
                Supervision temps reel des scopes patients, controle des alertes et priorisation clinique
                assistee.
              </div>
            </div>
            <div
              style={{
                display: "grid",
                gap: 14,
                gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              }}
            >
              <div
                style={{
                  padding: "18px 20px",
                  borderRadius: 18,
                  border: "1px solid rgba(125, 164, 203, 0.16)",
                  background: "linear-gradient(180deg, rgba(7, 22, 38, 0.92), rgba(8, 30, 50, 0.82))",
                  display: "grid",
                  gap: 10,
                  alignContent: "start",
                }}
              >
                <div style={{ color: "#88a1bb", fontSize: 11, letterSpacing: 1.4, textTransform: "uppercase" }}>
                  Flux temps reel
                </div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 10,
                    width: "fit-content",
                    padding: "10px 14px",
                    borderRadius: 14,
                    background: websocketBackground(wsStatus),
                    border: `1px solid ${websocketBorder(wsStatus)}`,
                    fontWeight: 800,
                    color: websocketText(wsStatus),
                  }}
                >
                  <span
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 999,
                      background: websocketColor(wsStatus),
                      boxShadow: `0 0 14px ${websocketGlow(wsStatus)}`,
                    }}
                  />
                  <span
                    style={{ color: websocketLabelText(wsStatus), fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}
                  >
                    WebSocket
                  </span>
                  <span style={{ color: websocketText(wsStatus) }}>{formatWebsocketStatus(wsStatus)}</span>
                </div>
                <div style={{ color: "#8ea6bd", fontSize: 13 }}>Mise a jour live des constantes et alertes.</div>
              </div>

              <div
                style={{
                  padding: "18px 20px",
                  borderRadius: 18,
                  border: "1px solid rgba(125, 164, 203, 0.16)",
                  background: "linear-gradient(180deg, rgba(7, 22, 38, 0.92), rgba(8, 30, 50, 0.82))",
                  display: "grid",
                  gap: 14,
                }}
              >
                <div style={{ color: "#88a1bb", fontSize: 11, letterSpacing: 1.4, textTransform: "uppercase" }}>
                  Etat du service
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <div
                    style={{
                      minWidth: 118,
                      padding: "12px 14px",
                      borderRadius: 14,
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(125, 164, 203, 0.12)",
                    }}
                  >
                    <div style={{ color: "#88a1bb", fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2 }}>
                      Scopes
                    </div>
                    <div style={{ marginTop: 6, fontSize: 26, fontWeight: 800 }}>{patients.length}</div>
                  </div>
                  <div
                    style={{
                      minWidth: 118,
                      padding: "12px 14px",
                      borderRadius: 14,
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(125, 164, 203, 0.12)",
                    }}
                  >
                    <div style={{ color: "#88a1bb", fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2 }}>
                      Alertes
                    </div>
                    <div style={{ marginTop: 6, fontSize: 26, fontWeight: 800 }}>{recentAlertCount}</div>
                  </div>
                  <div
                    style={{
                      minWidth: 160,
                      padding: "12px 14px",
                      borderRadius: 14,
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid rgba(125, 164, 203, 0.12)",
                    }}
                  >
                    <div style={{ color: "#88a1bb", fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2 }}>
                      Patients tries
                    </div>
                    <div style={{ marginTop: 6, fontSize: 26, fontWeight: 800 }}>
                      {prioritizedPatients.length}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <aside
            style={{
              flex: "0 1 380px",
              minWidth: 320,
              padding: 20,
              borderRadius: 22,
              border: "1px solid rgba(125, 164, 203, 0.16)",
              background: "linear-gradient(180deg, rgba(8, 22, 36, 0.94), rgba(8, 25, 42, 0.88))",
              display: "grid",
              gap: 14,
            }}
          >
            <div style={{ display: "grid", gap: 4 }}>
              <div style={{ color: "#88a1bb", fontSize: 11, letterSpacing: 1.4, textTransform: "uppercase" }}>
                Operations de supervision
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#f4f8fb" }}>Actions operateur</div>
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              <button
                type="button"
                disabled={refreshing}
                onClick={async () => {
                  setRefreshing(true);
                  try {
                    await refreshPatients();
                    window.setTimeout(() => {
                      loadDashboard().catch(console.error);
                      refreshPrioritization().catch(console.error);
                    }, 1500);
                  } catch (error) {
                    console.error(error);
                  } finally {
                    setRefreshing(false);
                  }
                }}
                style={{
                  border: 0,
                  background: refreshing ? "#64748b" : "#facc15",
                  color: "#0f172a",
                  padding: "11px 14px",
                  borderRadius: 12,
                  cursor: refreshing ? "default" : "pointer",
                  fontWeight: 800,
                }}
              >
                {refreshing ? "Refresh..." : "Refresh demo"}
              </button>
              <button
                type="button"
                disabled={prioritizing}
                onClick={() => {
                  refreshPrioritization().catch(console.error);
                }}
                style={{
                  border: 0,
                  background: prioritizing ? "#64748b" : "#e2e8f0",
                  color: "#0f172a",
                  padding: "11px 14px",
                  borderRadius: 12,
                  cursor: prioritizing ? "default" : "pointer",
                  fontWeight: 800,
                }}
              >
                {prioritizing ? "Analyse..." : "Prioriser les patients"}
              </button>
            </div>
            <div
              style={{
                padding: "14px 16px",
                borderRadius: 16,
                background: "rgba(255, 255, 255, 0.04)",
                border: "1px solid rgba(125, 164, 203, 0.12)",
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ color: "#88a1bb", fontSize: 11, letterSpacing: 1.2, textTransform: "uppercase" }}>
                Source priorisation
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#dbe8f5" }}>{prioritizationLabel}</div>
            </div>
          </aside>
        </div>
      </section>

      <section style={{ display: "grid", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "grid", gap: 4 }}>
            <div style={{ color: "#f8fafc", fontSize: 22, fontWeight: 800 }}>Vue moniteurs patients</div>
            <div style={{ color: "#cbd5e1", fontSize: 13 }}>
              {patients.length} scopes affiches, tri manuel et vues operateur conservees.
            </div>
          </div>
          <div style={{ display: "grid", gap: 8, justifyItems: "end" }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {([
              ["full", "Vue complete"],
              ["compact", "2 par ligne"],
              ["values", "Valeurs 5/ligne"],
            ] as Array<[PatientMonitorLayout, string]>).map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                onClick={() => setViewMode(mode)}
                style={{
                  border: 0,
                  borderRadius: 999,
                  padding: "10px 14px",
                  fontWeight: 800,
                  cursor: "pointer",
                  background: viewMode === mode ? "#0f172a" : "#e2e8f0",
                  color: viewMode === mode ? "#f8fafc" : "#0f172a",
                  boxShadow: viewMode === mode ? "0 10px 20px rgba(15, 23, 42, 0.18)" : "none",
                }}
              >
                {label}
              </button>
            ))}
            </div>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns:
              viewMode === "full"
                ? "minmax(0, 1fr)"
                : viewMode === "compact"
                  ? "repeat(2, minmax(0, 1fr))"
                  : "repeat(5, minmax(0, 1fr))",
            alignItems: "start",
          }}
        >
          {patients.map((patient) => {
            const patientAlerts = alerts.filter((alert) => alert.patient_id === patient.id).slice(0, 4);
            const patientPriority = prioritizationByPatient.get(patient.id);
            const frame = patientFrameStyle(patient.id, patientAlerts);
            return (
              <div
                key={patient.id}
                style={{
                  display: "grid",
                  gap: 10,
                  minWidth: 0,
                  padding: 12,
                  borderRadius: 26,
                  border: `2px solid ${frame.border}`,
                  background: frame.background,
                  boxShadow: frame.shadow,
                }}
              >
                <Link
                  to={`/patients/${patient.id}`}
                  style={{
                    textDecoration: "none",
                    color: "#0f172a",
                    borderRadius: 18,
                    border: `1px solid ${patientPriority ? priorityBorder(patientPriority.priority_level) : "rgba(148, 163, 184, 0.22)"}`,
                    background: patientPriority ? "rgba(248, 250, 252, 0.96)" : "rgba(248, 250, 252, 0.9)",
                    padding: "12px 14px",
                    display: "grid",
                    gap: 6,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <div style={{ fontWeight: 800 }}>
                      {patientPriority ? `#${patientPriority.priority_rank} ${patient.id}` : patient.id}
                    </div>
                    <div
                      style={{
                        color: patientPriority ? priorityText(patientPriority.priority_level) : "#475569",
                        fontWeight: 800,
                      }}
                    >
                      {patientPriority ? priorityLabel(patientPriority.priority_level) : "Priorite non evaluee"}
                    </div>
                  </div>
                  <div style={{ color: "#475569", fontSize: 14 }}>
                    {patientPriority?.reason ?? "Aucune priorisation IA disponible pour le moment."}
                  </div>
                </Link>
                <PatientMonitorStrip
                  patient={patient}
                  limits={alarmLimits[patient.id] ?? {}}
                  layoutMode={viewMode}
                  onUpdateLimits={(patientId, metric, next) => {
                    setAlarmLimits((current) => ({
                      ...current,
                      [patientId]: {
                        ...(current[patientId] ?? {}),
                        [metric]: next,
                      },
                    }));
                  }}
                />
                <AlertsPanel
                  alerts={patientAlerts}
                  onAck={async (alertId) => {
                    const updated = await ackAlert(alertId);
                    setAlerts((current) =>
                      current.map((alert) => (alert.id === updated.id ? updated : alert))
                    );
                  }}
                  title={`Alertes ${patient.id}`}
                />
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function patientFrameStyle(patientId: string, patientAlerts: AlertRecord[]): {
  border: string;
  background: string;
  shadow: string;
} {
  const accents = ["#38bdf8", "#34d399", "#f59e0b", "#f472b6", "#a78bfa"];
  const patientNumber = Number.parseInt(patientId.replace(/\D+/g, ""), 10) || 0;
  const accent = accents[(patientNumber - 1 + accents.length) % accents.length];
  const levels = patientAlerts.map((alert) => alert.level);

  if (levels.includes("CRITICAL")) {
    return {
      border: "#ef4444",
      background: "linear-gradient(180deg, rgba(127, 29, 29, 0.18), rgba(255, 255, 255, 0.96))",
      shadow: "0 16px 30px rgba(127, 29, 29, 0.18)",
    };
  }

  if (levels.includes("WARNING")) {
    return {
      border: "#f59e0b",
      background: "linear-gradient(180deg, rgba(180, 83, 9, 0.14), rgba(255, 255, 255, 0.97))",
      shadow: "0 16px 30px rgba(180, 83, 9, 0.12)",
    };
  }

  if (levels.includes("INFO")) {
    return {
      border: "#0ea5e9",
      background: "linear-gradient(180deg, rgba(14, 165, 233, 0.1), rgba(255, 255, 255, 0.98))",
      shadow: "0 16px 30px rgba(14, 165, 233, 0.12)",
    };
  }

  return {
    border: accent,
    background: `linear-gradient(180deg, ${hexToRgba(accent, 0.1)}, rgba(255, 255, 255, 0.98))`,
    shadow: `0 16px 30px ${hexToRgba(accent, 0.14)}`,
  };
}

function hexToRgba(hex: string, alpha: number): string {
  const normalized = hex.replace("#", "");
  const value = normalized.length === 3
    ? normalized
        .split("")
        .map((char) => `${char}${char}`)
        .join("")
    : normalized;
  const red = Number.parseInt(value.slice(0, 2), 16);
  const green = Number.parseInt(value.slice(2, 4), 16);
  const blue = Number.parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function priorityLabel(level: "high" | "medium" | "low"): string {
  switch (level) {
    case "high":
      return "Priorite haute";
    case "medium":
      return "Priorite moyenne";
    case "low":
      return "Priorite basse";
    default:
      return "Priorite non evaluee";
  }
}

function priorityText(level: "high" | "medium" | "low"): string {
  switch (level) {
    case "high":
      return "#b91c1c";
    case "medium":
      return "#c2410c";
    case "low":
      return "#0f766e";
    default:
      return "#475569";
  }
}

function priorityBorder(level: "high" | "medium" | "low"): string {
  switch (level) {
    case "high":
      return "#fecaca";
    case "medium":
      return "#fed7aa";
    case "low":
      return "#bbf7d0";
    default:
      return "#e2e8f0";
  }
}

function formatPrioritizationSource(status?: string, source?: string): string {
  if (status === "ollama" || source === "ollama") {
    return "Ollama actif";
  }
  if (status === "llm-unavailable") {
    return "Fallback local actif";
  }
  if (status === "disabled") {
    return "LLM desactive";
  }
  if (source === "rule-based") {
    return "Rule-based";
  }
  return "Indisponible";
}

function formatWebsocketStatus(status: string): string {
  switch (status) {
    case "open":
      return "Connecte";
    case "connecting":
      return "Connexion...";
    case "closed":
      return "Ferme";
    default:
      return status;
  }
}

function websocketColor(status: string): string {
  switch (status) {
    case "open":
      return "#22c55e";
    case "connecting":
      return "#f59e0b";
    case "closed":
      return "#ef4444";
    default:
      return "#94a3b8";
  }
}

function websocketGlow(status: string): string {
  switch (status) {
    case "open":
      return "rgba(34, 197, 94, 0.72)";
    case "connecting":
      return "rgba(245, 158, 11, 0.72)";
    case "closed":
      return "rgba(239, 68, 68, 0.72)";
    default:
      return "rgba(148, 163, 184, 0.52)";
  }
}

function websocketBackground(status: string): string {
  switch (status) {
    case "open":
      return "rgba(22, 163, 74, 0.18)";
    case "connecting":
      return "rgba(245, 158, 11, 0.18)";
    case "closed":
      return "rgba(239, 68, 68, 0.18)";
    default:
      return "rgba(15, 23, 42, 0.3)";
  }
}

function websocketBorder(status: string): string {
  switch (status) {
    case "open":
      return "rgba(34, 197, 94, 0.44)";
    case "connecting":
      return "rgba(245, 158, 11, 0.44)";
    case "closed":
      return "rgba(239, 68, 68, 0.44)";
    default:
      return "rgba(148, 163, 184, 0.16)";
  }
}

function websocketText(status: string): string {
  switch (status) {
    case "open":
      return "#dcfce7";
    case "connecting":
      return "#fef3c7";
    case "closed":
      return "#fee2e2";
    default:
      return "#f8fafc";
  }
}

function websocketLabelText(status: string): string {
  switch (status) {
    case "open":
      return "#bbf7d0";
    case "connecting":
      return "#fde68a";
    case "closed":
      return "#fecaca";
    default:
      return "#cbd5e1";
  }
}
