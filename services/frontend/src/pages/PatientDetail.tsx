import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ackAlert,
  exportCsvUrl,
  exportPdfUrl,
  getAlerts,
  getHistory,
  getMlPrediction,
  getPatients,
  getSummary,
  submitMlFeedback,
  trainMlModel
} from "../api/http";
import { connectLiveSocket } from "../api/ws";
import { AlertsPanel } from "../components/AlertsPanel";
import { ScenarioControls } from "../components/ScenarioControls";
import { VitalChart } from "../components/VitalChart";
import type { AlertRecord, LiveEvent } from "../types/alerts";
import type { MlPredictionResponse, PatientSummary, TrendPoint } from "../types/vitals";

export function PatientDetailPage() {
  const { patientId = "" } = useParams();
  const [patient, setPatient] = useState<PatientSummary | null>(null);
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [summary, setSummary] = useState("Chargement...");
  const [hours, setHours] = useState(0);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [mlPrediction, setMlPrediction] = useState<MlPredictionResponse | null>(null);
  const [mlPathology, setMlPathology] = useState("");
  const [mlComment, setMlComment] = useState("");
  const [mlStatus, setMlStatus] = useState("idle");
  const [mlMessage, setMlMessage] = useState("");

  const vitals = patient?.last_vitals;
  const currentPathology = vitals?.scenario_label ?? vitals?.scenario ?? "";
  const currentSurgeryType = vitals?.surgery_type ?? patient?.surgery_type ?? "";
  const currentScenario = vitals?.scenario_label ?? vitals?.scenario ?? "Cas clinique non disponible";

  useEffect(() => {
    let mounted = true;
    const loadBaseContext = async () => {
      const [patients, history] = await Promise.all([getPatients(), getHistory(patientId, 0)]);
      if (!mounted) {
        return;
      }
      const selected = patients.find((row) => row.id === patientId) ?? null;
      setPatient(selected);
      setPoints(history.points);
      if (!selected) {
        setSummary("Aucun contexte clinique trouve.");
        setAlerts([]);
        setMlPrediction(null);
      }
    };
    if (patientId) {
      loadBaseContext().catch(console.error);
    }
    return () => {
      mounted = false;
    };
  }, [patientId]);

  useEffect(() => {
    let mounted = true;
    const loadClinicalContext = async () => {
      const [caseAlerts, patientSummary, prediction] = await Promise.all([
        getAlerts(undefined, currentPathology, currentSurgeryType),
        getSummary(patientId),
        getMlPrediction(patientId).catch(() => null)
      ]);
      if (!mounted) {
        return;
      }
      setAlerts(caseAlerts);
      setSummary(patientSummary.summary);
      setMlPrediction(prediction);
      setMlPathology(prediction?.pathology ?? currentPathology);
    };
    if (patientId && currentPathology && currentSurgeryType) {
      loadClinicalContext().catch(console.error);
    }
    return () => {
      mounted = false;
    };
  }, [patientId, currentPathology, currentSurgeryType]);

  useEffect(() => {
    if (!patientId) {
      return;
    }
    const cleanup = connectLiveSocket((event: LiveEvent) => {
      if (event.patient_id !== patientId) {
        return;
      }
      if (event.type === "vitals") {
        setPatient((current) => (current ? { ...current, last_vitals: event.payload } : current));
        setPoints((current) => [
          ...current.slice(-999),
          {
            ts: event.payload.ts,
            values: {
              hr: event.payload.hr,
              spo2: event.payload.spo2,
              sbp: event.payload.sbp,
              dbp: event.payload.dbp,
              map: roundTam(event.payload.map),
              rr: event.payload.rr,
              temp: event.payload.temp,
              shock_index: event.payload.shock_index ?? 0
            }
          }
        ]);
      }
      if (event.type === "alert") {
        const payload = event.payload as AlertRecord;
        if (!matchesClinicalContext(payload, currentPathology, currentSurgeryType)) {
          return;
        }
        setAlerts((current) => [payload, ...current.filter((alert) => alert.id !== payload.id)].slice(0, 20));
      }
      if (event.type === "ack") {
        setAlerts((current) =>
          current.map((alert) => (alert.id === event.payload.id ? (event.payload as AlertRecord) : alert))
        );
      }
    }, setWsStatus);
    return cleanup;
  }, [patientId, currentPathology, currentSurgeryType]);

  async function refreshMlPrediction() {
    if (!patientId) {
      return;
    }
    setMlStatus("loading");
    try {
      const prediction = await getMlPrediction(patientId);
      setMlPrediction(prediction);
      setMlPathology(prediction.pathology);
      setMlMessage(
        prediction.model_ready
          ? `Score mis a jour pour ${prediction.pathology} / ${prediction.sample.surgery_type ?? "chirurgie en cours"}`
          : "Modele non entraine pour le moment, feedback requis."
      );
    } catch (error) {
      setMlMessage(error instanceof Error ? error.message : "Impossible de charger le score ML");
    } finally {
      setMlStatus("idle");
    }
  }

  async function handleMlFeedback(decision: "validate" | "invalidate", target?: "critical" | "non_critical") {
    if (!patientId) {
      return;
    }
    setMlStatus("saving");
    try {
      const response = await submitMlFeedback(patientId, {
        decision,
        target,
        pathology: mlPathology.trim() || mlPrediction?.pathology || currentPathology,
        comment: mlComment.trim()
      });
      setMlMessage(
        `Feedback enregistre: ${response.pathology} -> ${response.has_critical === 1 ? "critique" : "non critique"}`
      );
      setMlComment("");
      await refreshMlPrediction();
    } catch (error) {
      setMlMessage(error instanceof Error ? error.message : "Impossible d'enregistrer le feedback ML");
    } finally {
      setMlStatus("idle");
    }
  }

  async function handleMlTraining() {
    setMlStatus("training");
    try {
      const response = await trainMlModel();
      setMlMessage(
        response.accuracy === null
          ? `Modele entraine (${response.mode}, ${response.rows} lignes)`
          : `Modele entraine, accuracy ${response.accuracy.toFixed(2)} sur ${response.rows} lignes`
      );
      await refreshMlPrediction();
    } catch (error) {
      setMlMessage(error instanceof Error ? error.message : "Impossible d'entrainer le modele");
    } finally {
      setMlStatus("idle");
    }
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <Link to="/" style={{ color: "#0f766e", textDecoration: "none", fontWeight: 700 }}>
            Retour liste
          </Link>
          <h1 style={{ marginBottom: 6 }}>Fiche clinique active</h1>
          <div style={{ color: "#475569" }}>
            {currentPathology || "Cas clinique en cours"} - {currentSurgeryType || "chirurgie non renseignee"} - slot {patientId} - WebSocket {wsStatus}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" onClick={() => setHours(0)} style={hourButton(hours === 0)}>
            Depuis J0
          </button>
          <button type="button" onClick={() => setHours(1)} style={hourButton(hours === 1)}>
            1h
          </button>
          <button type="button" onClick={() => setHours(6)} style={hourButton(hours === 6)}>
            6h
          </button>
          <button type="button" onClick={() => setHours(24)} style={hourButton(hours === 24)}>
            24h
          </button>
          <a href={exportCsvUrl(patientId)} style={linkButton}>
            Export CSV
          </a>
          <a href={exportPdfUrl(patientId)} style={linkButton}>
            Export PDF
          </a>
        </div>
      </div>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        <MetricCard label="FC" value={vitals ? `${vitals.hr} bpm` : "-"} accentColor="#15803d" />
        <MetricCard label="SpO2" value={vitals ? `${vitals.spo2}%` : "-"} accentColor="#2563eb" />
        <MetricCard label="TA" value={vitals ? `${vitals.sbp}/${vitals.dbp}` : "-"} accentColor="#dc2626" />
        <MetricCard label="TAM" value={vitals ? `${roundTam(vitals.map)}` : "-"} accentColor="#dc2626" />
        <MetricCard label="FR" value={vitals ? `${vitals.rr}/min` : "-"} accentColor="#eab308" />
        <MetricCard label={"T\u00B0C"} value={vitals ? `${vitals.temp} \u00B0C` : "-"} accentColor="#7c3aed" />
      </section>

      <VitalChart points={points} rangeHours={hours} />

      <section style={{ display: "grid", gridTemplateColumns: "minmax(260px, 1fr) minmax(260px, 1fr)", gap: 16 }}>
        <ScenarioControls scenario={currentScenario} />
        <div style={{ background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
          <h3 style={{ marginTop: 0 }}>Resume</h3>
          <p style={{ color: "#334155" }}>{summary}</p>
          <div style={{ color: "#64748b", fontSize: 14 }}>
            Antecedents relies au cas: {(patient?.history ?? []).join(", ") || "non documentes"}
          </div>
        </div>
      </section>

      <section style={{ background: "#ffffff", borderRadius: 18, padding: 18, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)", display: "grid", gap: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <h3 style={{ margin: 0 }}>Validation ML</h3>
            <div style={{ color: "#64748b", fontSize: 14 }}>
              Le choix enregistre directement la bonne classe pour la combinaison pathologie + chirurgie.
            </div>
          </div>
          <button type="button" onClick={() => refreshMlPrediction()} style={secondaryButton}>
            Recalculer score
          </button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          <MetricCard
            label="Probabilite critique"
            value={mlPrediction?.probability !== null && mlPrediction?.probability !== undefined ? `${Math.round(mlPrediction.probability * 100)}%` : "N/A"}
          />
          <MetricCard label="Pathologie" value={mlPrediction?.pathology ?? (currentPathology || "N/A")} />
          <MetricCard label="Chirurgie" value={currentSurgeryType || "N/A"} />
          <MetricCard label="Modele" value={mlPrediction?.model_ready ? "Pret" : "En attente"} />
        </div>

        <label style={{ display: "grid", gap: 6, color: "#334155", fontWeight: 600 }}>
          Pathologie a confirmer
          <input
            value={mlPathology}
            onChange={(event) => setMlPathology(event.target.value)}
            placeholder="Ex: Hemorragie J+2"
            style={textInput}
          />
        </label>

        <label style={{ display: "grid", gap: 6, color: "#334155", fontWeight: 600 }}>
          Commentaire de validation
          <textarea
            value={mlComment}
            onChange={(event) => setMlComment(event.target.value)}
            placeholder="Pourquoi je confirme ou j'infirme ce cas"
            rows={3}
            style={{ ...textInput, resize: "vertical", minHeight: 88 }}
          />
        </label>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button type="button" onClick={() => handleMlFeedback("validate", "critical")} style={primaryButton} disabled={mlStatus !== "idle"}>
            Classer critique
          </button>
          <button type="button" onClick={() => handleMlFeedback("validate", "non_critical")} style={secondaryButton} disabled={mlStatus !== "idle"}>
            Classer non critique
          </button>
          <button type="button" onClick={() => handleMlTraining()} style={darkButton} disabled={mlStatus !== "idle"}>
            Entrainer le modele
          </button>
        </div>

        <div style={{ color: "#475569", fontSize: 14 }}>
          {mlStatus === "idle" ? mlMessage || "Aucun feedback enregistre dans cette session." : "Operation ML en cours..."}
        </div>

        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ fontWeight: 700, color: "#0f172a" }}>Derniers feedbacks du cas clinique</div>
          {(mlPrediction?.recent_feedback ?? []).length === 0 ? (
            <div style={{ color: "#64748b", fontSize: 14 }}>
              Pas encore de validation sur cette combinaison pathologie + chirurgie.
            </div>
          ) : (
            (mlPrediction?.recent_feedback ?? []).map((feedback) => (
              <div key={feedback.id} style={{ borderRadius: 12, background: "#f8fafc", padding: 12, border: "1px solid #e2e8f0" }}>
                <div style={{ fontWeight: 700, color: "#0f172a" }}>{feedback.label}</div>
                <div style={{ color: "#475569", fontSize: 14 }}>
                  {feedback.pathology ?? "pathologie non precisee"} - {feedback.surgery_type ?? "chirurgie non precisee"}
                </div>
                <div style={{ color: "#64748b", fontSize: 13 }}>
                  {feedback.has_critical === 1 ? "critique" : "non critique"} - {feedback.comment || "Sans commentaire"}
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <AlertsPanel
        title="Alertes du cas clinique"
        alerts={alerts}
        onAck={async (alertId) => {
          const updated = await ackAlert(alertId);
          setAlerts((current) => current.map((alert) => (alert.id === updated.id ? updated : alert)));
        }}
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
  accentColor = "#0f172a",
}: {
  label: string;
  value: string;
  accentColor?: string;
}) {
  return (
    <div
      style={{
        background: "#ffffff",
        borderRadius: 16,
        padding: 16,
        boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)",
        borderTop: `4px solid ${accentColor}`,
      }}
    >
      <div style={{ color: accentColor, fontSize: 13, fontWeight: 700 }}>{label}</div>
      <div style={{ fontWeight: 800, fontSize: 24 }}>{value}</div>
    </div>
  );
}

function matchesClinicalContext(alert: AlertRecord, pathology: string, surgeryType: string): boolean {
  const alertPathology = normalizeValue(
    String(alert.metric_snapshot.scenario_label ?? alert.metric_snapshot.scenario ?? "")
  );
  const alertSurgeryType = normalizeValue(String(alert.metric_snapshot.surgery_type ?? ""));
  return alertPathology === normalizeValue(pathology) && alertSurgeryType === normalizeValue(surgeryType);
}

function normalizeValue(value: string): string {
  return value.trim().toLowerCase();
}

function roundTam(value: number | undefined): number {
  return Math.round(Number(value ?? 0));
}

const linkButton: CSSProperties = {
  textDecoration: "none",
  background: "#0f172a",
  color: "#ffffff",
  padding: "10px 14px",
  borderRadius: 10
};

function hourButton(active: boolean): CSSProperties {
  return {
    border: 0,
    cursor: "pointer",
    background: active ? "#0f766e" : "#dbeafe",
    color: active ? "#ffffff" : "#0f172a",
    padding: "10px 14px",
    borderRadius: 10
  };
}

const textInput: CSSProperties = {
  width: "100%",
  border: "1px solid #cbd5e1",
  borderRadius: 12,
  padding: "12px 14px",
  font: "inherit",
  color: "#0f172a",
  background: "#ffffff"
};

const primaryButton: CSSProperties = {
  border: 0,
  cursor: "pointer",
  background: "#0f766e",
  color: "#ffffff",
  padding: "10px 14px",
  borderRadius: 10
};

const secondaryButton: CSSProperties = {
  border: 0,
  cursor: "pointer",
  background: "#dbeafe",
  color: "#0f172a",
  padding: "10px 14px",
  borderRadius: 10
};

const darkButton: CSSProperties = {
  border: 0,
  cursor: "pointer",
  background: "#0f172a",
  color: "#ffffff",
  padding: "10px 14px",
  borderRadius: 10
};
