import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ackAlert,
  analyzeClinicalPackage,
  exportCsvUrl,
  exportPdfUrl,
  getAlerts,
  getClinicalPackage,
  getDifferentialQuestionnaire,
  getHistory,
  getMlPrediction,
  getPatient,
  submitMlFeedback,
  trainMlModel
} from "../api/http";
import { connectLiveSocket } from "../api/ws";
import { AlertsPanel } from "../components/AlertsPanel";
import { ClinicalContextPanel } from "../components/ClinicalContextPanel";
import { DifferentialQuestionnaire } from "../components/DifferentialQuestionnaire";
import {
  ALARM_STORAGE_KEY,
  PatientMonitorStrip,
  type PatientAlarmLimits,
  loadStoredAlarmLimits,
} from "../components/PatientMonitorStrip";
import { VitalChart } from "../components/VitalChart";
import type { AlertRecord, LiveEvent } from "../types/alerts";
import type {
  ClinicalHypothesisRow,
  ClinicalContextSelection,
  ClinicalPackageResponse,
  MlPredictionResponse,
  PatientSummary,
  QuestionnaireSelectionResponse,
  QuestionnaireSubmission,
  TrendPoint,
  VitalPayload
} from "../types/vitals";

type AnalysisRestMode = "active" | "resting" | "stale";

interface AnalysisRestState {
  mode: AnalysisRestMode;
  anchorVitals: RestAnchorVitals | null;
  deltaSignals: string[];
  submittedAt: string | null;
}

type RestAnchorVitals = Pick<VitalPayload, "ts" | "hr" | "spo2" | "map" | "rr" | "temp" | "shock_index">;
const EMPTY_QUESTIONNAIRE_SELECTION: QuestionnaireSubmission = {
  responder: "patient",
  answers: [],
  comment: "",
};
const EMPTY_CLINICAL_CONTEXT: ClinicalContextSelection = {
  patient_factors: [],
  perioperative_context: [],
  free_text: "",
};

export function PatientDetailPage() {
  const { patientId = "" } = useParams();
  const [patient, setPatient] = useState<PatientSummary | null>(null);
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [summary, setSummary] = useState("Chargement...");
  const [summarySource, setSummarySource] = useState("indisponible");
  const [summaryLlmStatus, setSummaryLlmStatus] = useState("indisponible");
  const [summaryStatus, setSummaryStatus] = useState("idle");
  const [clinicalPackage, setClinicalPackage] = useState<ClinicalPackageResponse | null>(null);
  const [baselineClinicalPackage, setBaselineClinicalPackage] = useState<ClinicalPackageResponse | null>(null);
  const [questionnaireComparison, setQuestionnaireComparison] = useState<{
    before: ClinicalPackageResponse;
    after: ClinicalPackageResponse;
  } | null>(null);
  const [clinicalPackageStatus, setClinicalPackageStatus] = useState("idle");
  const [hours, setHours] = useState(0);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [mlPrediction, setMlPrediction] = useState<MlPredictionResponse | null>(null);
  const [mlPathology, setMlPathology] = useState("");
  const [mlComment, setMlComment] = useState("");
  const [mlStatus, setMlStatus] = useState("idle");
  const [mlMessage, setMlMessage] = useState("");
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireSelectionResponse | null>(null);
  const [questionnaireStatus, setQuestionnaireStatus] = useState("idle");
  const [questionnaireSubmitStatus, setQuestionnaireSubmitStatus] = useState("idle");
  const [clinicalContextSelection, setClinicalContextSelection] = useState<ClinicalContextSelection>(EMPTY_CLINICAL_CONTEXT);
  const [questionnaireSelection, setQuestionnaireSelection] = useState<QuestionnaireSubmission>(EMPTY_QUESTIONNAIRE_SELECTION);
  const [questionnaireCollapsed, setQuestionnaireCollapsed] = useState(false);
  const [analysisRestState, setAnalysisRestState] = useState<AnalysisRestState>({
    mode: "active",
    anchorVitals: null,
    deltaSignals: [],
    submittedAt: null,
  });
  const [alarmLimits, setAlarmLimits] = useState<Record<string, PatientAlarmLimits>>(() => loadStoredAlarmLimits());
  const defaultClinicalPackageRequestRef = useRef<Promise<ClinicalPackageResponse> | null>(null);

  const vitals = patient?.last_vitals;
  const currentPathology = vitals?.scenario_label ?? vitals?.scenario ?? "";
  const currentSurgeryType = vitals?.surgery_type ?? patient?.surgery_type ?? "";
  const currentPostopDay = vitals?.postop_day ?? patient?.postop_day;
  const activeAlerts = alerts.filter((alert) => alert.metric_snapshot.historical_backfill !== true);
  const historicalAlerts = alerts.filter((alert) => alert.metric_snapshot.historical_backfill === true);
  const questionnaireRestMessage = buildAnalysisRestMessage(analysisRestState);

  useEffect(() => {
    window.localStorage.setItem(ALARM_STORAGE_KEY, JSON.stringify(alarmLimits));
  }, [alarmLimits]);

  useEffect(() => {
    setSummary("Chargement...");
    setSummarySource("indisponible");
    setSummaryLlmStatus("indisponible");
    setClinicalPackage(null);
    setBaselineClinicalPackage(null);
    setQuestionnaireComparison(null);
    setQuestionnaire(null);
    setQuestionnaireSubmitStatus("idle");
    setClinicalContextSelection(EMPTY_CLINICAL_CONTEXT);
    setQuestionnaireSelection(EMPTY_QUESTIONNAIRE_SELECTION);
    setQuestionnaireCollapsed(false);
    setAnalysisRestState({
      mode: "active",
      anchorVitals: null,
      deltaSignals: [],
      submittedAt: null,
    });
    defaultClinicalPackageRequestRef.current = null;
  }, [patientId]);

  function requestDefaultClinicalPackage(targetPatientId: string): Promise<ClinicalPackageResponse> {
    if (defaultClinicalPackageRequestRef.current) {
      return defaultClinicalPackageRequestRef.current;
    }
    let pendingRequest: Promise<ClinicalPackageResponse>;
    pendingRequest = getClinicalPackage(targetPatientId).finally(() => {
      if (defaultClinicalPackageRequestRef.current === pendingRequest) {
        defaultClinicalPackageRequestRef.current = null;
      }
    });
    defaultClinicalPackageRequestRef.current = pendingRequest;
    return pendingRequest;
  }

  async function ensureComparisonBaseline(): Promise<ClinicalPackageResponse | null> {
    if (baselineClinicalPackage) {
      return baselineClinicalPackage;
    }
    if (clinicalPackage && !clinicalPackage.questionnaire_state) {
      setBaselineClinicalPackage(clinicalPackage);
      return clinicalPackage;
    }
    if (!patientId) {
      return null;
    }
    const response = await requestDefaultClinicalPackage(patientId);
    if (!response.questionnaire_state) {
      setBaselineClinicalPackage(response);
      return response;
    }
    return null;
  }

  function buildAnalysisPayload(): ClinicalContextSelection {
    const questionnairePayload = buildQuestionnairePayload(questionnaireSelection);
    return {
      patient_factors: [],
      perioperative_context: [],
      free_text: "",
      questionnaire: questionnairePayload,
    };
  }

  function applyClinicalPackageResponse(
    response: ClinicalPackageResponse,
    options: {
      setAsBaseline: boolean;
      comparisonBefore?: ClinicalPackageResponse | null;
    },
  ) {
    const { setAsBaseline, comparisonBefore } = options;
    setClinicalPackage(response);
    if (setAsBaseline) {
      setBaselineClinicalPackage(response);
    }
    setSummary(response.summary_text);
    setSummarySource(response.source);
    setSummaryLlmStatus(response.llm_status ?? response.source);
    setAnalysisRestState({
      mode: response.analysis_state.mode,
      anchorVitals: response.analysis_state.anchor_vitals
        ? {
            ts: response.analysis_state.anchor_vitals.ts ?? "",
            hr: response.analysis_state.anchor_vitals.hr,
            spo2: response.analysis_state.anchor_vitals.spo2,
            map: response.analysis_state.anchor_vitals.map,
            rr: response.analysis_state.anchor_vitals.rr,
            temp: response.analysis_state.anchor_vitals.temp,
            shock_index: response.analysis_state.anchor_vitals.shock_index ?? 0,
          }
        : null,
      deltaSignals: response.analysis_state.delta_signals ?? [],
      submittedAt: response.analysis_state.submitted_at ?? response.analysis_state.generated_at ?? null,
    });
    setQuestionnaireSelection(response.questionnaire_state ?? EMPTY_QUESTIONNAIRE_SELECTION);
    setQuestionnaireCollapsed(response.analysis_state.mode !== "active");
    if (comparisonBefore && response.questionnaire_state) {
      setQuestionnaireComparison({
        before: comparisonBefore,
        after: response,
      });
    } else {
      setQuestionnaireComparison(null);
    }
  }

  function handleQuestionnaireChange(next: QuestionnaireSubmission) {
    setQuestionnaireSelection(next);
    setAnalysisRestState((current) => {
      if (current.mode === "active") {
        return current;
      }
      return {
        ...current,
        mode: "stale",
        deltaSignals: dedupeStrings([
          ...current.deltaSignals,
          "Reponses questionnaire modifiees depuis la derniere analyse",
        ]),
      };
    });
  }

  async function refreshDefaultClinicalPackage() {
    if (!patientId) {
      return;
    }
    setSummaryStatus("loading");
    setClinicalPackageStatus("loading");
    try {
      const response = await requestDefaultClinicalPackage(patientId);
      applyClinicalPackageResponse(response, { setAsBaseline: true });
    } finally {
      setSummaryStatus("idle");
      setClinicalPackageStatus("idle");
    }
  }

  async function refreshDefaultSummary() {
    await refreshDefaultClinicalPackage();
  }

  useEffect(() => {
    let mounted = true;
    const loadBaseContext = async () => {
      const [selected, history] = await Promise.all([getPatient(patientId), getHistory(patientId, 0)]);
      if (!mounted) {
        return;
      }
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
      const [caseAlerts, prediction] = await Promise.all([
        getAlerts(patientId, currentPathology, currentSurgeryType),
        getMlPrediction(patientId).catch(() => null)
      ]);
      if (!mounted) {
        return;
      }
      setAlerts(caseAlerts);
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
    let mounted = true;
    const loadClinicalPackage = async () => {
      if (!patientId || !currentPathology || !currentSurgeryType) {
        return;
      }
      setSummaryStatus("loading");
      setClinicalPackageStatus("loading");
      try {
        const response = await requestDefaultClinicalPackage(patientId);
        if (mounted) {
          applyClinicalPackageResponse(response, { setAsBaseline: true });
        }
      } catch (error) {
        if (mounted) {
          setSummary("Impossible de charger l'analyse clinique.");
          setSummarySource("indisponible");
          setSummaryLlmStatus("indisponible");
          setClinicalPackage(null);
          setBaselineClinicalPackage(null);
          setQuestionnaireComparison(null);
        }
      } finally {
        if (mounted) {
          setSummaryStatus("idle");
          setClinicalPackageStatus("idle");
        }
      }
    };
    loadClinicalPackage().catch(console.error);
    return () => {
      mounted = false;
    };
  }, [patientId, currentPathology, currentSurgeryType]);

  useEffect(() => {
    let mounted = true;
    const loadQuestionnaire = async () => {
      if (!patientId) {
        return;
      }
      setQuestionnaireStatus("loading");
      try {
        const response = await getDifferentialQuestionnaire(patientId);
        if (!mounted) {
          return;
        }
        setQuestionnaire(response);
      } catch (error) {
        if (mounted) {
          setQuestionnaire(null);
          setQuestionnaireCollapsed(false);
        }
      } finally {
        if (mounted) {
          setQuestionnaireStatus("idle");
        }
      }
    };
    loadQuestionnaire().catch(console.error);
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
        setAnalysisRestState((current) => {
          if (current.mode !== "resting" || !current.anchorVitals) {
            return current;
          }
          const deltaSignals = detectAnalysisDelta(current.anchorVitals, event.payload);
          if (deltaSignals.length === 0) {
            return current;
          }
          return {
            ...current,
            mode: "stale",
            deltaSignals,
          };
        });
      }
      if (event.type === "alert") {
        const payload = event.payload as AlertRecord;
        if (!matchesClinicalContext(payload, currentPathology, currentSurgeryType)) {
          return;
        }
        setAlerts((current) => [payload, ...current.filter((alert) => alert.id !== payload.id)].slice(0, 20));
        if (payload.level === "CRITICAL") {
          setAnalysisRestState((current) => {
            if (current.mode !== "resting") {
              return current;
            }
            return {
              ...current,
              mode: "stale",
              deltaSignals: dedupeStrings([
                ...current.deltaSignals,
                `Nouvelle alerte critique: ${payload.title}`,
              ]),
            };
          });
        }
      }
      if (event.type === "ack") {
        setAlerts((current) =>
          current.map((alert) => (alert.id === event.payload.id ? (event.payload as AlertRecord) : alert))
        );
      }
    }, setWsStatus);
    return cleanup;
  }, [patientId, currentPathology, currentSurgeryType]);

  async function refreshSummaryWithContext() {
    if (!patientId) {
      return;
    }
    setQuestionnaireSubmitStatus("loading");
    setSummaryStatus("loading");
    setClinicalPackageStatus("loading");
    const analysisPayload = buildAnalysisPayload();
    const questionnairePayload = analysisPayload.questionnaire;
    if (!questionnairePayload) {
      setQuestionnaireComparison(null);
    }
    try {
      const comparisonBaseline = questionnairePayload
        ? await ensureComparisonBaseline()
        : baselineClinicalPackage ?? clinicalPackage;
      const response = await analyzeClinicalPackage(patientId, analysisPayload);
      applyClinicalPackageResponse(response, {
        setAsBaseline: !questionnairePayload,
        comparisonBefore: questionnairePayload ? comparisonBaseline : null,
      });
    } catch (error) {
      setSummary(error instanceof Error ? error.message : "Impossible de lancer l'analyse IA contextualisee.");
    } finally {
      setQuestionnaireSubmitStatus("idle");
      setSummaryStatus("idle");
      setClinicalPackageStatus("idle");
    }
  }

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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
          alignItems: "center",
          padding: "16px 18px",
          borderRadius: 20,
          background: "linear-gradient(135deg, rgba(7, 26, 52, 0.86), rgba(14, 65, 105, 0.72))",
          border: "1px solid rgba(148, 197, 255, 0.24)",
          boxShadow: "0 18px 40px rgba(2, 12, 27, 0.28)",
          backdropFilter: "blur(6px)",
        }}
      >
        <div>
          <Link to="/" style={{ color: "#a7f3d0", textDecoration: "none", fontWeight: 700 }}>
            Retour liste
          </Link>
          <h1
            style={{
              marginBottom: 6,
              marginTop: 8,
              color: "#f8fafc",
              textShadow: "0 2px 12px rgba(15, 23, 42, 0.45)",
            }}
          >
            {currentSurgeryType || "chirurgie non renseignee"}
            {typeof currentPostopDay === "number" ? ` - J+${currentPostopDay}` : ""}
          </h1>
          <div style={{ color: "#dbeafe", fontWeight: 500 }}>
            {currentSurgeryType || "chirurgie non renseignee"} - slot {patientId} - WebSocket {wsStatus}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <a href={exportCsvUrl(patientId)} style={linkButton}>
            Export CSV
          </a>
          <a href={exportPdfUrl(patientId)} style={linkButton}>
            Export PDF
          </a>
        </div>
      </div>

      {patient ? (
        <PatientMonitorStrip
          patient={patient}
          limits={alarmLimits[patient.id] ?? {}}
          onUpdateLimits={(targetPatientId, metric, next) => {
            setAlarmLimits((current) => ({
              ...current,
              [targetPatientId]: {
                ...(current[targetPatientId] ?? {}),
                [metric]: next,
              },
            }));
          }}
          showDetailLink={false}
          headerTitle="Scope du patient"
        />
      ) : null}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
        <AlertsPanel
          title="Alertes actives"
          alerts={activeAlerts}
          onAck={async (alertId) => {
            const updated = await ackAlert(alertId);
            setAlerts((current) => current.map((alert) => (alert.id === updated.id ? updated : alert)));
          }}
        />
        <AlertsPanel title="Alertes historiques" alerts={historicalAlerts} />
      </section>

      <section style={{ display: "grid", gap: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ fontWeight: 800, color: "#0f172a" }}>Historique des constantes vitales</div>
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
          </div>
        </div>
        <VitalChart points={points} rangeHours={hours} />
      </section>

      <ClinicalContextPanel
        value={clinicalContextSelection}
        onChange={setClinicalContextSelection}
        title="Antecedents medicaux chirurgicaux"
        description="Retrouve ici les selections d'antecedents et facteurs cliniques. Elles sont preparees pour une future exploitation IA de conduite a tenir."
        showAnalyzeButton={false}
      />

      <section>
        <div style={{ background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <h3 style={{ marginTop: 0, marginBottom: 0 }}>Resume</h3>
            <div style={{ display: "grid", justifyItems: "end", gap: 4 }}>
              <span style={{ color: "#64748b", fontSize: 13 }}>
                {summaryStatus === "loading" ? "Analyse IA contextualisee en cours..." : "Resume clinique"}
              </span>
              <span style={{ color: sourceColor(summaryLlmStatus), fontSize: 13, fontWeight: 700 }}>
                {formatLlmStatus(summaryLlmStatus, summarySource)}
              </span>
            </div>
          </div>
          <p style={{ color: "#334155" }}>{summary}</p>
        </div>
      </section>

      <DifferentialQuestionnaire
        modules={questionnaire?.modules ?? []}
        triggerSummary={questionnaire?.trigger_summary ?? []}
        value={questionnaireSelection}
        onChange={handleQuestionnaireChange}
        onSubmit={refreshSummaryWithContext}
        collapsed={questionnaireCollapsed}
        onToggleCollapsed={() => setQuestionnaireCollapsed((current) => !current)}
        restState={analysisRestState.mode}
        restMessage={questionnaireRestMessage}
        loading={
          questionnaireStatus === "loading" || questionnaireSubmitStatus === "loading"
        }
      />

      <section style={{ background: "#ffffff", borderRadius: 18, padding: 18, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)", display: "grid", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <div>
            <h3 style={{ margin: 0 }}>Analyse clinique IA</h3>
            <div style={{ color: "#64748b", fontSize: 14 }}>
              Synthese structuree, explication des alertes, hypotheses compatibles, evolution et priorites de recontrole.
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ color: "#475569", fontSize: 13, fontWeight: 700 }}>
              Source: {formatLlmStatus(clinicalPackage?.llm_status, clinicalPackage?.source)}
            </div>
            {analysisRestState.mode !== "active" ? (
              <div
                style={{
                  borderRadius: 999,
                  padding: "6px 10px",
                  background: analysisRestState.mode === "stale" ? "#fee2e2" : "#dcfce7",
                  color: analysisRestState.mode === "stale" ? "#b91c1c" : "#166534",
                  fontSize: 12,
                  fontWeight: 800,
                }}
              >
                {analysisRestState.mode === "stale" ? "Nouvelle derive detectee" : "LLM au repos"}
              </div>
            ) : null}
            {analysisRestState.mode !== "active" ? (
              <button type="button" onClick={() => refreshSummaryWithContext()} style={darkButton} disabled={clinicalPackageStatus === "loading" || summaryStatus === "loading"}>
                {clinicalPackageStatus === "loading" || summaryStatus === "loading" ? "Reevaluation..." : "Reevaluation"}
              </button>
            ) : (
              <button type="button" onClick={() => refreshDefaultClinicalPackage()} style={secondaryButton} disabled={clinicalPackageStatus === "loading"}>
                {clinicalPackageStatus === "loading" ? "Analyse..." : "Actualiser l'analyse"}
              </button>
            )}
            <button type="button" onClick={() => refreshDefaultSummary()} style={secondaryButton} disabled={summaryStatus === "loading"}>
              {summaryStatus === "loading" ? "Resume..." : "Actualiser le resume"}
            </button>
          </div>
        </div>

        {clinicalPackage ? (
          <>
            <div style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ fontWeight: 700, color: "#0f172a" }}>Score explicatif</div>
                <div
                  style={{
                    borderRadius: 999,
                    padding: "6px 10px",
                    background: scoreAccentTint(clinicalPackage.explanatory_score.level),
                    color: scoreAccentColor(clinicalPackage.explanatory_score.level),
                    fontWeight: 800,
                  }}
                >
                  {clinicalPackage.explanatory_score.score}/100
                </div>
              </div>
              <div style={{ color: scoreAccentColor(clinicalPackage.explanatory_score.level), fontSize: 14, fontWeight: 700 }}>
                {formatExplanatoryLevel(clinicalPackage.explanatory_score.level)}
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, color: "#334155" }}>
                {clinicalPackage.explanatory_score.reasons.map((item, index) => (
                  <li key={`score-${index}-${item}`} style={{ marginBottom: 4 }}>
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 8 }}>
              <div style={{ fontWeight: 700, color: "#0f172a" }}>Synthese structuree</div>
              <div style={{ color: "#334155" }}>{clinicalPackage.structured_synthesis}</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
              <RiskExplainCard
                title="Evolution"
                level={formatTrajectory(clinicalPackage.trajectory_status)}
                items={[clinicalPackage.trajectory_explanation]}
                emptyMessage="Aucune evolution detaillee disponible."
              />
              <RiskExplainCard
                title="Coherence clinique observee"
                level="Analyse"
                items={[clinicalPackage.scenario_consistency]}
                emptyMessage="Pas de coherence de scenario disponible."
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
              <div style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 8 }}>
                <div style={{ fontWeight: 700, color: "#0f172a" }}>Explication des alertes</div>
                {clinicalPackage.alert_explanations.length === 0 ? (
                  <div style={{ color: "#64748b", fontSize: 14 }}>Aucune explication supplementaire disponible.</div>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 18, color: "#334155" }}>
                    {clinicalPackage.alert_explanations.map((item, index) => (
                      <li key={`alert-${index}-${item}`} style={{ marginBottom: 4 }}>
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 8 }}>
                <div style={{ fontWeight: 700, color: "#0f172a" }}>A recontroler</div>
                {clinicalPackage.recheck_recommendations.length === 0 ? (
                  <div style={{ color: "#64748b", fontSize: 14 }}>Pas de recommandation supplementaire.</div>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 18, color: "#334155" }}>
                    {clinicalPackage.recheck_recommendations.map((item, index) => (
                      <li key={`recheck-${index}-${item}`} style={{ marginBottom: 4 }}>
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div style={{ display: "grid", gap: 10 }}>
              <div style={{ fontWeight: 700, color: "#0f172a" }}>Hypotheses par compatibilite</div>
              {clinicalPackage.hypothesis_ranking.length === 0 ? (
                <div style={{ color: "#64748b", fontSize: 14 }}>Aucune hypothese detaillee disponible.</div>
              ) : (
                clinicalPackage.hypothesis_ranking.map((row) => (
                  <div key={`${row.label}-${row.compatibility}`} style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                      <div style={{ fontWeight: 700, color: "#0f172a" }}>{row.label}</div>
                      <div style={{ display: "grid", justifyItems: "end", gap: 2 }}>
                        <div style={{ color: compatibilityColor(row.compatibility), fontWeight: 800 }}>
                          {formatCompatibility(row.compatibility)}
                        </div>
                        <div style={{ color: "#0f172a", fontSize: 13, fontWeight: 800 }}>
                          {row.compatibility_percent}%
                        </div>
                      </div>
                    </div>
                    <div style={{ color: "#334155", fontSize: 14 }}>
                      <strong>Arguments pour:</strong> {row.arguments_for.join(" ; ")}
                    </div>
                    <div style={{ color: "#475569", fontSize: 14 }}>
                      <strong>Arguments contre:</strong> {row.arguments_against.join(" ; ")}
                    </div>
                  </div>
                ))
              )}
            </div>

            {questionnaireComparison ? (
              <div style={{ display: "grid", gap: 10 }}>
                <div style={{ fontWeight: 700, color: "#0f172a" }}>Hypotheses apres questionnaire</div>
                <div style={{ color: "#64748b", fontSize: 14 }}>
                  Comparatif avant / apres validation du questionnaire differentiel.
                </div>
                {buildHypothesisComparisonRows(
                  questionnaireComparison.before.hypothesis_ranking,
                  questionnaireComparison.after.hypothesis_ranking
                ).map((row) => (
                  <div key={row.label} style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                      <div style={{ fontWeight: 700, color: "#0f172a" }}>{row.label}</div>
                      <div style={{ color: comparisonDeltaColor(row.delta), fontWeight: 800 }}>
                        {formatComparisonDelta(row.delta)}
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                      <div style={comparisonCell}>
                        <div style={{ color: "#64748b", fontSize: 12, fontWeight: 700 }}>Avant questionnaire</div>
                        <div style={{ color: "#0f172a", fontSize: 20, fontWeight: 800 }}>{row.beforePercent}%</div>
                        <div style={{ color: comparisonCompatibilityColor(row.beforeCompatibility, row.beforePercent), fontSize: 13, fontWeight: 700 }}>
                          {formatComparisonCompatibility(row.beforeCompatibility, row.beforePercent)}
                        </div>
                      </div>
                      <div style={comparisonCell}>
                        <div style={{ color: "#64748b", fontSize: 12, fontWeight: 700 }}>Apres questionnaire</div>
                        <div style={{ color: "#0f172a", fontSize: 20, fontWeight: 800 }}>{row.afterPercent}%</div>
                        <div style={{ color: comparisonCompatibilityColor(row.afterCompatibility, row.afterPercent), fontSize: 13, fontWeight: 700 }}>
                          {formatComparisonCompatibility(row.afterCompatibility, row.afterPercent)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 8 }}>
              <div style={{ fontWeight: 700, color: "#0f172a" }}>Resume de transmission</div>
              <div style={{ color: "#334155" }}>{clinicalPackage.handoff_summary}</div>
            </div>
          </>
        ) : (
          <div style={{ color: "#64748b", fontSize: 14 }}>
            {clinicalPackageStatus === "loading" ? "Analyse clinique IA en cours..." : "Pack d'analyse clinique indisponible pour le moment."}
          </div>
        )}
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
            label="Criticite immediate"
            value={mlPrediction ? `${mlPrediction.immediate_criticality.score}%` : "N/A"}
            accentColor={scoreAccentColor(mlPrediction?.immediate_criticality.level)}
          />
          <MetricCard
            label="Risque evolutif"
            value={mlPrediction ? `${mlPrediction.evolving_risk.score}%` : "N/A"}
            accentColor={scoreAccentColor(mlPrediction?.evolving_risk.level)}
          />
          <MetricCard
            label="Score ML historique"
            value={
              mlPrediction?.probability !== null && mlPrediction?.probability !== undefined
                ? `${Math.round(mlPrediction.probability * 100)}%`
                : "N/A"
            }
            accentColor="#0f172a"
          />
          <MetricCard label="Modele" value={mlPrediction?.model_ready ? "Pret" : "En attente"} />
          <MetricCard label="Pathologie" value={mlPrediction?.pathology ?? (currentPathology || "N/A")} />
          <MetricCard label="Chirurgie" value={currentSurgeryType || "N/A"} />
        </div>

        <div style={{ display: "grid", gap: 10 }}>
          <RiskExplainCard
            title="Seuils critiques immediats"
            level={formatRiskLevel(mlPrediction?.immediate_criticality.level)}
            items={mlPrediction?.immediate_criticality.triggered_thresholds ?? []}
            emptyMessage="Aucun seuil critique immediat franchi a cet instant."
          />
          <RiskExplainCard
            title="Signaux evolutifs depuis J0"
            level={formatRiskLevel(mlPrediction?.evolving_risk.level)}
            items={mlPrediction?.evolving_risk.signals ?? []}
            emptyMessage="Pas de derive evolutive significative detectee sur la trajectoire."
          />
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

function RiskExplainCard({
  title,
  level,
  items,
  emptyMessage,
}: {
  title: string;
  level: string;
  items: string[];
  emptyMessage: string;
}) {
  return (
    <div style={{ borderRadius: 14, background: "#f8fafc", padding: 14, border: "1px solid #e2e8f0", display: "grid", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 700, color: "#0f172a" }}>{title}</div>
        <div style={{ color: "#475569", fontSize: 13, fontWeight: 700 }}>{level}</div>
      </div>
      {items.length === 0 ? (
        <div style={{ color: "#64748b", fontSize: 14 }}>{emptyMessage}</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, color: "#334155" }}>
          {items.slice(0, 6).map((item, index) => (
            <li key={`risk-${index}-${item}`} style={{ marginBottom: 4 }}>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function buildQuestionnairePayload(
  selection: QuestionnaireSubmission
): QuestionnaireSubmission | undefined {
  return selection.answers.length > 0 || selection.comment.trim() || selection.responder !== "patient"
    ? selection
    : undefined;
}

function detectAnalysisDelta(anchor: RestAnchorVitals, next: VitalPayload): string[] {
  const signals: string[] = [];
  if (Math.abs(next.hr - anchor.hr) >= ANALYSIS_DELTA_TRIGGER.hr) {
    signals.push(`FC ${formatSignedValue(next.hr - anchor.hr)} bpm`);
  }
  if (Math.abs(next.spo2 - anchor.spo2) >= ANALYSIS_DELTA_TRIGGER.spo2) {
    signals.push(`SpO2 ${formatSignedValue(next.spo2 - anchor.spo2)} pts`);
  }
  if (Math.abs(next.map - anchor.map) >= ANALYSIS_DELTA_TRIGGER.map) {
    signals.push(`TAM ${formatSignedValue(next.map - anchor.map)} mmHg`);
  }
  if (Math.abs(next.rr - anchor.rr) >= ANALYSIS_DELTA_TRIGGER.rr) {
    signals.push(`FR ${formatSignedValue(next.rr - anchor.rr)}/min`);
  }
  if (Math.abs(next.temp - anchor.temp) >= ANALYSIS_DELTA_TRIGGER.temp) {
    signals.push(`T ${formatSignedFloat(next.temp - anchor.temp)} C`);
  }
  if (Math.abs((next.shock_index ?? 0) - anchor.shock_index) >= ANALYSIS_DELTA_TRIGGER.shockIndex) {
    signals.push(`shock index ${formatSignedFloat((next.shock_index ?? 0) - anchor.shock_index)}`);
  }
  return signals;
}

function buildAnalysisRestMessage(state: AnalysisRestState): string {
  if (state.mode === "resting") {
    return `Analyse au repos apres questionnaire${state.submittedAt ? ` depuis ${formatSubmittedAt(state.submittedAt)}` : ""}. Nouvelle reevaluation uniquement sur action manuelle.`;
  }
  if (state.mode === "stale") {
    const details = state.deltaSignals.join(" ; ") || "delta trigger backend franchi";
    return `Nouvelle derive clinique depuis la derniere analyse: ${details}. Reevaluation conseillee.`;
  }
  return "";
}

function buildHypothesisComparisonRows(
  beforeRows: ClinicalHypothesisRow[],
  afterRows: ClinicalHypothesisRow[]
): Array<{
  label: string;
  beforePercent: number;
  afterPercent: number;
  delta: number;
  beforeCompatibility: "high" | "medium" | "low";
  afterCompatibility: "high" | "medium" | "low";
}> {
  const beforeIndex = new Map(beforeRows.map((row) => [row.label, row]));
  const afterIndex = new Map(afterRows.map((row) => [row.label, row]));
  const labels = Array.from(new Set([...beforeIndex.keys(), ...afterIndex.keys()]));

  return labels
    .map((label) => {
      const before = beforeIndex.get(label);
      const after = afterIndex.get(label);
      return {
        label,
        beforePercent: before?.compatibility_percent ?? 0,
        afterPercent: after?.compatibility_percent ?? 0,
        delta: (after?.compatibility_percent ?? 0) - (before?.compatibility_percent ?? 0),
        beforeCompatibility: before?.compatibility ?? "low",
        afterCompatibility: after?.compatibility ?? "low",
      };
    })
    .sort((left, right) => {
      if (right.afterPercent !== left.afterPercent) {
        return right.afterPercent - left.afterPercent;
      }
      return right.beforePercent - left.beforePercent;
    });
}

function dedupeStrings(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)));
}

function formatSignedValue(value: number): string {
  return `${value >= 0 ? "+" : ""}${Math.round(value)}`;
}

function formatSignedFloat(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  return `${rounded >= 0 ? "+" : ""}${rounded.toFixed(2)}`;
}

function formatSubmittedAt(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "tout a l'heure";
  }
  return parsed.toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
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

function formatRiskLevel(level?: string): string {
  switch (level) {
    case "critique":
      return "Critique";
    case "seuil_critique_franchi":
      return "Seuil critique franchi";
    case "tres_eleve":
      return "Tres eleve";
    case "eleve":
      return "Eleve";
    case "modere":
      return "Modere";
    case "faible":
      return "Faible";
    case "stable":
      return "Stable";
    default:
      return "Non evalue";
  }
}

function scoreAccentColor(level?: string): string {
  switch (level) {
    case "critical":
    case "critique":
    case "seuil_critique_franchi":
    case "tres_eleve":
      return "#dc2626";
    case "high":
    case "eleve":
    case "modere":
      return "#ea580c";
    case "medium":
      return "#c2410c";
    case "low":
    case "faible":
    case "stable":
      return "#15803d";
    default:
      return "#0f172a";
  }
}

function scoreAccentTint(level?: string): string {
  switch (level) {
    case "critical":
    case "critique":
    case "seuil_critique_franchi":
    case "tres_eleve":
      return "#fee2e2";
    case "high":
    case "eleve":
    case "modere":
      return "#ffedd5";
    case "medium":
      return "#fed7aa";
    case "low":
    case "faible":
    case "stable":
      return "#dcfce7";
    default:
      return "#e2e8f0";
  }
}

function formatExplanatoryLevel(level?: string): string {
  switch (level) {
    case "critical":
      return "Criticite tres elevee";
    case "high":
      return "Criticite elevee";
    case "medium":
      return "Criticite moderee";
    case "low":
      return "Criticite faible";
    default:
      return "Criticite non evaluee";
  }
}

function formatCompatibility(level: "high" | "medium" | "low"): string {
  switch (level) {
    case "high":
      return "Compatibilite forte";
    case "medium":
      return "Compatibilite moyenne";
    case "low":
      return "Compatibilite faible";
    default:
      return "Compatibilite non evaluee";
  }
}

function compatibilityColor(level: "high" | "medium" | "low"): string {
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

function formatComparisonCompatibility(level: "high" | "medium" | "low", percent: number): string {
  if (percent <= 0) {
    return "Non retenue";
  }
  return formatCompatibility(level);
}

function comparisonCompatibilityColor(level: "high" | "medium" | "low", percent: number): string {
  if (percent <= 0) {
    return "#64748b";
  }
  return compatibilityColor(level);
}

function formatComparisonDelta(delta: number): string {
  if (delta > 0) {
    return `+${delta} pts`;
  }
  if (delta < 0) {
    return `${delta} pts`;
  }
  return "stable";
}

function comparisonDeltaColor(delta: number): string {
  if (delta > 0) {
    return "#15803d";
  }
  if (delta < 0) {
    return "#b91c1c";
  }
  return "#475569";
}

function formatTrajectory(status: string): string {
  switch (status) {
    case "worsening":
      return "Aggravation";
    case "switching":
      return "Bascule";
    case "recovering":
      return "Amelioration";
    case "stable":
      return "Stabilite";
    default:
      return "Non precise";
  }
}

function formatLlmStatus(status?: string, source?: string): string {
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

function sourceColor(status?: string): string {
  if (status === "ollama") {
    return "#15803d";
  }
  if (status === "llm-unavailable") {
    return "#c2410c";
  }
  if (status === "disabled") {
    return "#64748b";
  }
  return "#475569";
}

const ANALYSIS_DELTA_TRIGGER = {
  hr: 10,
  spo2: 2,
  map: 5,
  rr: 3,
  temp: 0.3,
  shockIndex: 0.08,
} as const;

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

const comparisonCell: CSSProperties = {
  borderRadius: 12,
  border: "1px solid #e2e8f0",
  background: "#ffffff",
  padding: 12,
  display: "grid",
  gap: 4
};
