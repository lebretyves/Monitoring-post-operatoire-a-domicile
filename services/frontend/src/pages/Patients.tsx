import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getAlerts, getPatients, refreshPatients } from "../api/http";
import { connectLiveSocket } from "../api/ws";
import { AlertsPanel } from "../components/AlertsPanel";
import type { AlertRecord, LiveEvent } from "../types/alerts";
import type { PatientSummary } from "../types/vitals";

export function PatientsPage() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshNote, setRefreshNote] = useState(
    "Refresh demo: PAT-001 reste en Constantes Normales, les autres slots tirent des cas cliniques complets."
  );

  async function loadDashboard() {
    const [patientRows, alertRows] = await Promise.all([getPatients(), getAlerts()]);
    setPatients(patientRows);
    setAlerts(alertRows.slice(0, 8));
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
          </div>
        </div>
        <div style={{ marginTop: 12, color: "#dbeafe", maxWidth: 1040 }}>{refreshNote}</div>
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
