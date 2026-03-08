import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getAlerts, getPatients, getPrioritizedPatients, refreshPatients } from "../api/http";
import { connectLiveSocket } from "../api/ws";
import { AlertsPanel } from "../components/AlertsPanel";
import type { AlertRecord, LiveEvent } from "../types/alerts";
import type { PatientPrioritizationRow, PatientSummary } from "../types/vitals";

export function PatientsPage() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [prioritizedPatients, setPrioritizedPatients] = useState<PatientPrioritizationRow[]>([]);
  const [prioritizationSource, setPrioritizationSource] = useState("indisponible");
  const [prioritizationStatus, setPrioritizationStatus] = useState("indisponible");
  const [wsStatus, setWsStatus] = useState("connecting");
  const [refreshing, setRefreshing] = useState(false);
  const [prioritizing, setPrioritizing] = useState(false);
  const [refreshNote, setRefreshNote] = useState(
    "Refresh demo: PAT-001 reste en Constantes Normales, les autres slots tirent des cas cliniques complets."
  );

  async function loadDashboard() {
    const [patientRows, alertRows] = await Promise.all([getPatients(), getAlerts()]);
    setPatients(patientRows);
    setAlerts(alertRows.slice(0, 8));
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
    refreshPrioritization().catch(console.error);
    const cleanup = connectLiveSocket((event: LiveEvent) => {
      if (event.type === "vitals") {
        setPatients((current) =>
          current.map((patient) =>
            patient.id === event.patient_id ? { ...patient, last_vitals: event.payload } : patient
          )
        );
      }
      if (event.type === "alert") {
        setAlerts((current) => [event.payload as AlertRecord, ...current].slice(0, 8));
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
      <section style={{ padding: 24, borderRadius: 24, background: "linear-gradient(135deg, #0f172a, #164e63)", color: "#f8fafc" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ margin: 0 }}>Monitoring post-operatoire a domicile</h1>
            <p style={{ maxWidth: 760 }}>
              Vue d'ensemble des patients, des constantes vitales live et des alertes generees par le backend.
            </p>
          </div>
          <div style={{ display: "grid", gap: 10, justifyItems: "end" }}>
            <div style={{ alignSelf: "center", fontWeight: 700 }}>WebSocket: {wsStatus}</div>
            <button
              type="button"
              disabled={refreshing}
              onClick={async () => {
                setRefreshing(true);
                try {
                  const result = await refreshPatients();
                  setRefreshNote(
                    `${result.rule} Repartition: ${result.assignments
                      .map((item) => `${item.patient_id} -> ${item.case_label ?? item.scenario_label ?? item.scenario}`)
                      .join(" | ")}`
                  );
                  window.setTimeout(() => {
                    loadDashboard().catch(console.error);
                    refreshPrioritization().catch(console.error);
                  }, 1500);
                } catch (error) {
                  console.error(error);
                  setRefreshNote("Echec du refresh demo.");
                } finally {
                  setRefreshing(false);
                }
              }}
              style={{
                border: 0,
                background: refreshing ? "#64748b" : "#facc15",
                color: "#0f172a",
                padding: "10px 14px",
                borderRadius: 10,
                cursor: refreshing ? "default" : "pointer",
                fontWeight: 800
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
                padding: "10px 14px",
                borderRadius: 10,
                cursor: prioritizing ? "default" : "pointer",
                fontWeight: 800
              }}
            >
              {prioritizing ? "Analyse..." : "Prioriser les patients"}
            </button>
          </div>
        </div>
        <div style={{ marginTop: 12, color: "#dbeafe", maxWidth: 1040 }}>{refreshNote}</div>
      </section>

      <section style={{ background: "#ffffff", borderRadius: 20, padding: 18, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)", display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <h2 style={{ margin: 0 }}>Priorisation IA</h2>
            <div style={{ color: "#64748b", fontSize: 14 }}>
              Classement des patients a revoir en premier selon constantes, alertes et tendance evolutive.
            </div>
          </div>
          <div style={{ color: "#475569", fontSize: 13, fontWeight: 700 }}>
            Source: {formatPrioritizationSource(prioritizationStatus, prioritizationSource)}
          </div>
        </div>
        {prioritizedPatients.length === 0 ? (
          <div style={{ color: "#64748b", fontSize: 14 }}>Aucune priorisation disponible pour le moment.</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
            {prioritizedPatients.map((row) => (
              <Link
                key={`${row.patient_id}-${row.priority_rank}`}
                to={`/patients/${row.patient_id}`}
                style={{
                  textDecoration: "none",
                  color: "#0f172a",
                  borderRadius: 16,
                  background: "#f8fafc",
                  padding: 14,
                  border: `1px solid ${priorityBorder(row.priority_level)}`,
                  display: "grid",
                  gap: 8,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                  <div style={{ fontWeight: 800 }}>#{row.priority_rank} {row.patient_id}</div>
                  <div style={{ color: priorityText(row.priority_level), fontWeight: 800 }}>
                    {priorityLabel(row.priority_level)}
                  </div>
                </div>
                <div style={{ color: "#475569", fontSize: 14 }}>{row.reason}</div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
        {patients.map((patient) => {
          const vitals = patient.last_vitals;
          return (
            <Link
              key={patient.id}
              to={`/patients/${patient.id}`}
              style={{ textDecoration: "none", color: "#0f172a", background: "#ffffff", borderRadius: 20, padding: 18, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}
            >
              <div style={{ fontSize: 13, color: "#64748b" }}>{patient.room}</div>
              <h2 style={{ marginBottom: 4 }}>{patient.id}</h2>
              <div style={{ marginBottom: 12, color: "#475569" }}>
                {patient.surgery_type} - J+{patient.postop_day}
              </div>
              <div style={{ marginBottom: 12, fontSize: 13, color: "#0f766e", fontWeight: 700 }}>
                Scenario: {vitals?.scenario_label ?? vitals?.scenario ?? "en attente"}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <Metric label="FC" value={vitals?.hr ? `${vitals.hr} bpm` : "-"} accentColor="#15803d" />
                <Metric label="SpO2" value={vitals?.spo2 ? `${vitals.spo2}%` : "-"} accentColor="#2563eb" />
                <Metric label="TAM" value={vitals?.map ? `${roundTam(vitals.map)}` : "-"} accentColor="#dc2626" />
                <Metric label="FR" value={vitals?.rr ? `${vitals.rr}/min` : "-"} accentColor="#eab308" />
              </div>
            </Link>
          );
        })}
      </section>

      <AlertsPanel alerts={alerts} />
    </div>
  );
}

function Metric({
  label,
  value,
  accentColor = "#0f172a",
}: {
  label: string;
  value: string;
  accentColor?: string;
}) {
  return (
    <div style={{ background: "#f8fafc", borderRadius: 14, padding: 12, borderTop: `4px solid ${accentColor}` }}>
      <div style={{ fontSize: 12, color: accentColor, fontWeight: 700 }}>{label}</div>
      <div style={{ fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function roundTam(value: number | undefined): number {
  return Math.round(Number(value ?? 0));
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
