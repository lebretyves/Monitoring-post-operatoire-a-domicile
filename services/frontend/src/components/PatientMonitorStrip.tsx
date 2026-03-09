import { useMemo, useState, useSyncExternalStore, type CSSProperties } from "react";
import { Link } from "react-router-dom";

import type { PatientSummary, VitalPayload } from "../types/vitals";

export type AlarmMetricId = "hr" | "spo2" | "sbp" | "rr" | "temp";

export interface AlarmLimitSet {
  low: number;
  high: number;
}

export type PatientAlarmLimits = Partial<Record<AlarmMetricId, AlarmLimitSet>>;
export type PatientMonitorLayout = "full" | "compact" | "values";

export const ALARM_STORAGE_KEY = "postop-monitor-strip-alarms-v1";

interface PatientMonitorStripProps {
  patient: PatientSummary;
  limits: PatientAlarmLimits;
  onUpdateLimits: (patientId: string, metric: AlarmMetricId, next: AlarmLimitSet) => void;
  showDetailLink?: boolean;
  headerTitle?: string;
  layoutMode?: PatientMonitorLayout;
  phaseSeconds?: number;
}

const MONITOR_COLORS = {
  hr: "#2dd36f",
  spo2: "#3ea7ff",
  sbp: "#ff5a5f",
  rr: "#f7d046",
  temp: "#b86bff",
  gridMajor: "rgba(35, 73, 115, 0.24)",
  gridMinor: "rgba(35, 73, 115, 0.12)",
  chrome: "#9fb9d7",
  surface: "#06131f",
  surfaceRaised: "#0d1d2f",
};

const DEFAULT_LIMITS: Record<AlarmMetricId, AlarmLimitSet> = {
  hr: { low: 50, high: 120 },
  spo2: { low: 92, high: 100 },
  sbp: { low: 90, high: 140 },
  rr: { low: 8, high: 24 },
  temp: { low: 36.0, high: 38.0 },
};

const METRIC_META: Record<
  AlarmMetricId,
  { label: string; unit: string; color: string; step: number; describe: (vitals: VitalPayload) => string }
> = {
  hr: {
    label: "FC",
    unit: "bpm",
    color: MONITOR_COLORS.hr,
    step: 1,
    describe: (vitals) => `${Math.round(vitals.hr)}`
  },
  spo2: {
    label: "SpO2",
    unit: "%",
    color: MONITOR_COLORS.spo2,
    step: 1,
    describe: (vitals) => `${Math.round(vitals.spo2)}`
  },
  sbp: {
    label: "TA",
    unit: "mmHg",
    color: MONITOR_COLORS.sbp,
    step: 1,
    describe: (vitals) => `${Math.round(vitals.sbp)}/${Math.round(vitals.dbp)}  TAM ${Math.round(vitals.map)}`
  },
  rr: {
    label: "FR",
    unit: "/min",
    color: MONITOR_COLORS.rr,
    step: 1,
    describe: (vitals) => `${Math.round(vitals.rr)}`
  },
  temp: {
    label: "T°C",
    unit: "°C",
    color: MONITOR_COLORS.temp,
    step: 0.1,
    describe: (vitals) => `${vitals.temp.toFixed(1)}`
  },
};

const SWEEP_SECONDS = 5.8;
const WAVE_SAMPLES = 220;
const SHARED_CLOCK_INTERVAL_MS = 70;

let sharedClockMs = Date.now();
let sharedClockTimer: number | null = null;
const sharedClockListeners = new Set<() => void>();

export function PatientMonitorStrip({
  patient,
  limits,
  onUpdateLimits,
  showDetailLink = true,
  headerTitle = "Scope patient",
  layoutMode = "full",
  phaseSeconds,
}: PatientMonitorStripProps) {
  const vitals = patient.last_vitals ?? null;
  const phaseMs = useSharedMonitorClock(phaseSeconds);
  const [activeMetric, setActiveMetric] = useState<AlarmMetricId | null>(null);
  const compact = layoutMode === "compact";
  const valuesOnly = layoutMode === "values";

  const sweepProgress = ((phaseMs / 1000) % SWEEP_SECONDS) / SWEEP_SECONDS;
  const monitorSignals = useMemo(() => buildMonitorSignals(patient.id, vitals, phaseMs / 1000), [patient.id, vitals, phaseMs]);

  if (!vitals) {
    return (
      <article
        style={{
          background: MONITOR_COLORS.surface,
          borderRadius: 24,
          padding: 18,
          color: "#e2eefb",
          boxShadow: "0 14px 28px rgba(2, 6, 23, 0.18)"
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <div style={{ color: "#9fb9d7", fontSize: 13, letterSpacing: 1.1, textTransform: "uppercase" }}>
              Monitoring
            </div>
            <div style={{ fontSize: 28, fontWeight: 800 }}>{patient.id}</div>
          </div>
          {showDetailLink ? (
            <Link to={`/patients/${patient.id}`} style={detailLinkStyle}>
              Ouvrir le dossier
            </Link>
          ) : null}
        </div>
        <div style={{ marginTop: 24, color: "#7b96b3" }}>En attente de constantes live.</div>
      </article>
    );
  }

  return (
    <article
      style={{
        position: "relative",
        background:
          "radial-gradient(circle at top right, rgba(30, 64, 175, 0.18), transparent 28%), linear-gradient(180deg, #07111b, #050b12 72%)",
        borderRadius: compact || valuesOnly ? 18 : 24,
        padding: compact || valuesOnly ? 14 : 18,
        color: "#e2eefb",
        boxShadow: "0 18px 34px rgba(2, 6, 23, 0.22)",
        border: "1px solid rgba(71, 111, 160, 0.24)"
      }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: valuesOnly ? 8 : 14, flexWrap: "wrap" }}>
        <div style={{ display: "grid", gap: 4 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            {!valuesOnly ? (
              <span style={{ color: "#6bd3ff", fontSize: compact || valuesOnly ? 11 : 13, fontWeight: 800, letterSpacing: 1.1, textTransform: "uppercase" }}>
                {headerTitle}
              </span>
            ) : null}
            <span style={pillStyle}>{patient.id}</span>
            <span style={pillStyle}>J+{patient.postop_day}</span>
            <span style={pillStyle}>{patient.room}</span>
          </div>
          <div style={{ fontSize: compact || valuesOnly ? 13 : 15, color: "#d6e6fb", fontWeight: 700 }}>
            {valuesOnly ? truncateLabel(patient.surgery_type, 28) : patient.surgery_type}
          </div>
          <div style={{ fontSize: compact || valuesOnly ? 11 : 13, color: "#8fb8d8" }}>
            {valuesOnly ? truncateLabel(vitals.scenario_label ?? vitals.scenario, 32) : `Scenario observe: ${vitals.scenario_label ?? vitals.scenario}`}
          </div>
        </div>
        {showDetailLink && !valuesOnly ? (
          <Link to={`/patients/${patient.id}`} style={detailLinkStyle}>
            Ouvrir le dossier
          </Link>
        ) : null}
      </header>

      {valuesOnly ? (
        <div
          style={{
            display: "grid",
            gap: 8,
            borderRadius: 16,
            background: "linear-gradient(180deg, rgba(8, 20, 32, 0.96), rgba(4, 10, 18, 0.96))",
            border: "1px solid rgba(71, 111, 160, 0.18)",
            padding: "10px 10px 12px",
            boxShadow: "inset 0 0 0 1px rgba(148, 184, 224, 0.04)",
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", gap: 8 }}>
            <div style={{ color: "#9fb9d7", fontSize: 10, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 800 }}>
              Mini scope numerique
            </div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "3px 7px",
                borderRadius: 999,
                background: "rgba(15, 23, 42, 0.82)",
                border: "1px solid rgba(71, 111, 160, 0.18)",
                color: "#c7d6e7",
                fontSize: 10,
                fontWeight: 700,
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: 999,
                  background: "#22c55e",
                  boxShadow: "0 0 10px rgba(34, 197, 94, 0.7)",
                }}
              />
              LIVE
            </div>
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            {(Object.keys(METRIC_META) as AlarmMetricId[]).map((metricId) => {
              const meta = METRIC_META[metricId];
              const metricLimits = limits[metricId] ?? DEFAULT_LIMITS[metricId];
              const value = metricId === "sbp" ? vitals.sbp : vitals[metricId];
              const outOfRange = value < metricLimits.low || value > metricLimits.high;
              return (
                <button
                  key={metricId}
                  type="button"
                  onClick={() => setActiveMetric((current) => (current === metricId ? null : metricId))}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "44px minmax(0, 1fr)",
                    gap: 8,
                    alignItems: "baseline",
                    textAlign: "left",
                    borderRadius: 12,
                    border: `1px solid ${outOfRange ? meta.color : "rgba(159, 185, 215, 0.14)"}`,
                    background: outOfRange ? "rgba(168, 26, 42, 0.16)" : "rgba(9, 19, 31, 0.82)",
                    color: "#eff7ff",
                    padding: "8px 9px",
                    cursor: "pointer",
                    boxShadow: activeMetric === metricId ? `0 0 0 1px ${meta.color}` : "none",
                  }}
                >
                  <div style={{ display: "grid", gap: 2 }}>
                    <span style={{ color: meta.color, fontWeight: 900, fontSize: 11, letterSpacing: 0.7 }}>{meta.label}</span>
                    <span style={{ color: "#5f7d9c", fontSize: 9, fontWeight: 700 }}>{meta.unit}</span>
                  </div>
                  <div style={{ display: "grid", gap: 2 }}>
                    <span
                      style={{
                        color: meta.color,
                        fontWeight: 900,
                        fontSize: metricId === "sbp" ? 15 : 22,
                        lineHeight: 1,
                        fontVariantNumeric: "tabular-nums",
                        textShadow: "0 0 12px rgba(255,255,255,0.08)",
                      }}
                    >
                      {meta.describe(vitals)}
                    </span>
                    <span style={{ color: outOfRange ? meta.color : "#6f8ba8", fontSize: 9, fontWeight: 700 }}>
                      {formatLimitSummary(metricLimits)}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {showDetailLink ? (
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <Link
                to={`/patients/${patient.id}`}
                style={{
                  textDecoration: "none",
                  color: "#04121e",
                  background: "#d4efff",
                  padding: "8px 10px",
                  borderRadius: 10,
                  fontWeight: 800,
                  fontSize: 11,
                }}
              >
                Voir fiche
              </Link>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateRows: compact ? "repeat(4, minmax(42px, 1fr))" : "repeat(4, minmax(54px, 1fr))",
              gap: compact ? 6 : 8,
              background: "rgba(7, 18, 30, 0.58)",
              borderRadius: compact ? 16 : 20,
              padding: compact ? 10 : 12,
              border: "1px solid rgba(71, 111, 160, 0.18)"
            }}
          >
            <WaveRow
              label="ECG"
              color={MONITOR_COLORS.hr}
              signal={monitorSignals.ecg}
              sweepProgress={sweepProgress}
              metricValue={`${Math.round(vitals.hr)} bpm`}
              compact={compact}
            />
            <WaveRow
              label="TA"
              color={MONITOR_COLORS.sbp}
              signal={monitorSignals.art}
              sweepProgress={sweepProgress}
              metricValue={`${Math.round(vitals.sbp)}/${Math.round(vitals.dbp)}  TAM ${Math.round(vitals.map)}`}
              compact={compact}
            />
            <WaveRow
              label="SpO2"
              color={MONITOR_COLORS.spo2}
              signal={monitorSignals.pleth}
              sweepProgress={sweepProgress}
              metricValue={`${Math.round(vitals.spo2)}%`}
              compact={compact}
            />
            <WaveRow
              label="FR"
              color={MONITOR_COLORS.rr}
              signal={monitorSignals.resp}
              sweepProgress={sweepProgress}
              metricValue={`${Math.round(vitals.rr)}/min`}
              compact={compact}
            />
          </div>

          <div
            style={{
              marginTop: 12,
              display: "grid",
              gridTemplateColumns: compact
                ? "repeat(auto-fit, minmax(130px, 1fr))"
                : "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 10,
            }}
          >
            {(Object.keys(METRIC_META) as AlarmMetricId[]).map((metricId) => {
              const meta = METRIC_META[metricId];
              const metricLimits = limits[metricId] ?? DEFAULT_LIMITS[metricId];
              const value = metricId === "sbp" ? vitals.sbp : vitals[metricId];
              const outOfRange = value < metricLimits.low || value > metricLimits.high;
              return (
                <button
                  key={metricId}
                  type="button"
                  onClick={() => setActiveMetric((current) => (current === metricId ? null : metricId))}
                  style={{
                    textAlign: "left",
                    borderRadius: 18,
                    border: `1px solid ${outOfRange ? meta.color : "rgba(159, 185, 215, 0.18)"}`,
                    background: outOfRange ? "rgba(168, 26, 42, 0.18)" : "rgba(13, 29, 47, 0.92)",
                    color: "#eff7ff",
                    padding: "12px 14px",
                    cursor: "pointer",
                    boxShadow: activeMetric === metricId ? `0 0 0 1px ${meta.color}` : "none",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                    <span style={{ color: meta.color, fontWeight: 800, fontSize: 13 }}>{meta.label}</span>
                    <span style={{ color: outOfRange ? meta.color : "#6f8ba8", fontSize: 11 }}>
                      {formatLimitSummary(metricLimits)}
                    </span>
                  </div>
                  <div
                    style={{
                      marginTop: 6,
                      fontWeight: 800,
                      fontSize: metricId === "sbp" ? 18 : 24,
                      lineHeight: 1.1
                    }}
                  >
                    {meta.describe(vitals)}
                  </div>
                </button>
              );
            })}
          </div>
        </>
      )}

      {activeMetric ? (
        <AlarmEditor
          patientId={patient.id}
          metricId={activeMetric}
          value={limits[activeMetric] ?? DEFAULT_LIMITS[activeMetric]}
          onClose={() => setActiveMetric(null)}
          onSave={(next) => onUpdateLimits(patient.id, activeMetric, next)}
        />
      ) : null}
    </article>
  );
}

function useSharedMonitorClock(externalPhaseSeconds?: number): number {
  const sharedPhaseMs = useSyncExternalStore(subscribeSharedClock, getSharedClockSnapshot, getSharedClockSnapshot);
  if (typeof externalPhaseSeconds === "number") {
    return externalPhaseSeconds * 1000;
  }
  return sharedPhaseMs;
}

function subscribeSharedClock(listener: () => void): () => void {
  sharedClockListeners.add(listener);
  if (sharedClockTimer === null && typeof window !== "undefined") {
    sharedClockTimer = window.setInterval(() => {
      sharedClockMs = Date.now();
      sharedClockListeners.forEach((notify) => notify());
    }, SHARED_CLOCK_INTERVAL_MS);
  }
  return () => {
    sharedClockListeners.delete(listener);
    if (sharedClockListeners.size === 0 && sharedClockTimer !== null) {
      window.clearInterval(sharedClockTimer);
      sharedClockTimer = null;
    }
  };
}

function getSharedClockSnapshot(): number {
  return sharedClockMs;
}

export function loadStoredAlarmLimits(): Record<string, PatientAlarmLimits> {
  try {
    const raw = window.localStorage.getItem(ALARM_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Record<string, Partial<Record<AlarmMetricId, AlarmLimitSet>>>;
    return parsed ?? {};
  } catch (error) {
    console.warn("Impossible de relire les alarmes locales du scope.", error);
    return {};
  }
}

function WaveRow({
  label,
  color,
  signal,
  sweepProgress,
  metricValue,
  compact = false,
}: {
  label: string;
  color: string;
  signal: SignalDefinition;
  sweepProgress: number;
  metricValue: string;
  compact?: boolean;
}) {
  const cursorX = Math.max(8, Math.min(signal.width - 8, sweepProgress * signal.width));
  const markerPoint = pointAtX(signal.points, cursorX);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: compact ? "62px minmax(0, 1fr) 92px" : "84px minmax(0, 1fr) 118px",
        gap: compact ? 8 : 10,
        alignItems: "center",
        minHeight: compact ? 42 : 54,
      }}
    >
      <div style={{ color, fontWeight: 800, letterSpacing: 1, fontSize: compact ? 11 : 13 }}>{label}</div>
      <div style={{ position: "relative", height: compact ? 42 : 54, borderRadius: 12, overflow: "hidden", background: "rgba(2, 9, 16, 0.42)" }}>
        <svg viewBox={`0 0 ${signal.width} ${signal.height}`} preserveAspectRatio="none" width="100%" height="100%">
          <defs>
            <clipPath id={`${signal.id}-clip`}>
              <rect x="0" y="0" width={cursorX} height={signal.height} />
            </clipPath>
            <filter id={`${signal.id}-glow`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2.6" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <Grid width={signal.width} height={signal.height} />
          <path d={signal.path} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2" />
          <path
            d={signal.path}
            fill="none"
            stroke={color}
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            clipPath={`url(#${signal.id}-clip)`}
            filter={`url(#${signal.id}-glow)`}
          />
          <circle cx={cursorX} cy={markerPoint.y} r="2.8" fill={color} filter={`url(#${signal.id}-glow)`} />
        </svg>
      </div>
      <div style={{ color, fontWeight: 800, fontSize: compact ? 12 : 14, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{metricValue}</div>
    </div>
  );
}

function AlarmEditor({
  patientId,
  metricId,
  value,
  onClose,
  onSave,
}: {
  patientId: string;
  metricId: AlarmMetricId;
  value: AlarmLimitSet;
  onClose: () => void;
  onSave: (next: AlarmLimitSet) => void;
}) {
  const [draft, setDraft] = useState<AlarmLimitSet>(value);
  const meta = METRIC_META[metricId];

  useEffect(() => {
    setDraft(value);
  }, [value]);

  return (
    <div
      style={{
        position: "absolute",
        right: 18,
        bottom: 18,
        width: 286,
        borderRadius: 18,
        background: "rgba(5, 15, 25, 0.98)",
        border: `1px solid ${meta.color}`,
        boxShadow: "0 18px 36px rgba(2, 6, 23, 0.36)",
        padding: 16,
        zIndex: 2,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
        <div>
          <div style={{ color: meta.color, fontSize: 12, fontWeight: 800, letterSpacing: 1.1, textTransform: "uppercase" }}>
            Alarmes {meta.label}
          </div>
          <div style={{ color: "#e8f2ff", fontWeight: 800 }}>{patientId}</div>
        </div>
        <button type="button" onClick={onClose} style={ghostButtonStyle}>
          Fermer
        </button>
      </div>

      <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
        <label style={editorLabelStyle}>
          Seuil bas
          <input
            type="number"
            step={meta.step}
            value={draft.low}
            onChange={(event) => setDraft((current) => ({ ...current, low: Number(event.target.value) }))}
            style={editorInputStyle}
          />
        </label>
        <label style={editorLabelStyle}>
          Seuil haut
          <input
            type="number"
            step={meta.step}
            value={draft.high}
            onChange={(event) => setDraft((current) => ({ ...current, high: Number(event.target.value) }))}
            style={editorInputStyle}
          />
        </label>
      </div>

      <div style={{ marginTop: 12, color: "#8fb8d8", fontSize: 12 }}>
        Reglage local du scope. Unite: {meta.unit}.
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 16 }}>
        <button type="button" onClick={() => setDraft(DEFAULT_LIMITS[metricId])} style={ghostButtonStyle}>
          Valeurs par defaut
        </button>
        <button
          type="button"
          onClick={() => {
            onSave(normalizeLimits(draft, DEFAULT_LIMITS[metricId]));
            onClose();
          }}
          style={{
            border: 0,
            background: meta.color,
            color: "#04121e",
            borderRadius: 10,
            padding: "8px 12px",
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          Enregistrer
        </button>
      </div>
    </div>
  );
}

function Grid({ width, height }: { width: number; height: number }) {
  const majorStep = 32;
  const minorStep = 8;
  const lines: JSX.Element[] = [];

  for (let x = 0; x <= width; x += minorStep) {
    lines.push(
      <line
        key={`x-${x}`}
        x1={x}
        x2={x}
        y1={0}
        y2={height}
        stroke={x % majorStep === 0 ? MONITOR_COLORS.gridMajor : MONITOR_COLORS.gridMinor}
        strokeWidth={x % majorStep === 0 ? 0.8 : 0.45}
      />
    );
  }

  for (let y = 0; y <= height; y += minorStep) {
    lines.push(
      <line
        key={`y-${y}`}
        x1={0}
        x2={width}
        y1={y}
        y2={y}
        stroke={y % majorStep === 0 ? MONITOR_COLORS.gridMajor : MONITOR_COLORS.gridMinor}
        strokeWidth={y % majorStep === 0 ? 0.8 : 0.45}
      />
    );
  }

  return <>{lines}</>;
}

interface SignalDefinition {
  id: string;
  width: number;
  height: number;
  points: Array<{ x: number; y: number }>;
  path: string;
}

function buildMonitorSignals(patientId: string, vitals: VitalPayload | null, nowSeconds: number): {
  ecg: SignalDefinition;
  art: SignalDefinition;
  pleth: SignalDefinition;
  resp: SignalDefinition;
} {
  const width = 1200;
  const height = 54;
  const hr = clamp(vitals?.hr ?? 72, 45, 160);
  const rr = clamp(vitals?.rr ?? 16, 6, 36);
  const pulsePressure = Math.max(20, (vitals?.sbp ?? 122) - (vitals?.dbp ?? 74));
  const spo2 = clamp(vitals?.spo2 ?? 98, 75, 100);

  return {
    ecg: buildSignal(`${patientId}-ecg`, width, height, (t) => ecgWave(t, hr)),
    art: buildSignal(`${patientId}-art`, width, height, (t) => arterialWave(t, hr, pulsePressure)),
    pleth: buildSignal(`${patientId}-pleth`, width, height, (t) => plethWave(t, hr, rr, spo2)),
    resp: buildSignal(`${patientId}-resp`, width, height, (t) => respirationWave(t, rr, nowSeconds)),
  };
}

function buildSignal(
  id: string,
  width: number,
  height: number,
  sampler: (timeSeconds: number) => number
): SignalDefinition {
  const points: Array<{ x: number; y: number }> = [];
  for (let index = 0; index <= WAVE_SAMPLES; index += 1) {
    const x = (index / WAVE_SAMPLES) * width;
    const time = (index / WAVE_SAMPLES) * SWEEP_SECONDS;
    const normalized = clamp(sampler(time), 0, 1);
    const y = height - normalized * (height - 8) - 4;
    points.push({ x, y });
  }
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  return { id, width, height, points, path };
}

function ecgWave(time: number, hr: number): number {
  const cycle = 60 / hr;
  const phase = (time % cycle) / cycle;
  const baseline = 0.5 + 0.015 * Math.sin((time / cycle) * Math.PI * 2 * 0.5);

  if (phase < 0.12) {
    return baseline;
  }
  if (phase < 0.2) {
    return baseline + 0.06 * smoothPulse((phase - 0.12) / 0.08);
  }
  if (phase < 0.28) {
    return baseline;
  }
  if (phase < 0.315) {
    return baseline - 0.08 * ((phase - 0.28) / 0.035);
  }
  if (phase < 0.34) {
    return baseline + 0.95 * ((phase - 0.315) / 0.025);
  }
  if (phase < 0.37) {
    return baseline + 0.95 - 1.08 * ((phase - 0.34) / 0.03);
  }
  if (phase < 0.45) {
    return baseline;
  }
  if (phase < 0.66) {
    return baseline + 0.18 * smoothPulse((phase - 0.45) / 0.21);
  }
  return baseline;
}

function arterialWave(time: number, hr: number, pulsePressure: number): number {
  const cycle = 60 / hr;
  const phase = (time % cycle) / cycle;
  const amplitude = clamp((pulsePressure - 18) / 48, 0.28, 0.92);
  const floor = 0.12;

  if (phase < 0.08) {
    return floor + amplitude * easeOutCubic(phase / 0.08);
  }
  if (phase < 0.17) {
    return floor + amplitude * (1 - 0.08 * ((phase - 0.08) / 0.09));
  }
  if (phase < 0.42) {
    return floor + amplitude * (0.92 - 0.48 * ((phase - 0.17) / 0.25));
  }
  if (phase < 0.47) {
    return floor + amplitude * (0.44 - 0.12 * ((phase - 0.42) / 0.05));
  }
  if (phase < 0.53) {
    return floor + amplitude * (0.32 + 0.11 * ((phase - 0.47) / 0.06));
  }
  return floor + amplitude * (0.43 * Math.exp(-3.1 * (phase - 0.53)));
}

function plethWave(time: number, hr: number, rr: number, spo2: number): number {
  const cycle = 60 / hr;
  const phase = (time % cycle) / cycle;
  const respMod = 0.92 + 0.08 * Math.sin((time / (60 / rr)) * Math.PI * 2);
  const amplitude = clamp(((spo2 - 82) / 18) * respMod, 0.22, 1);
  const floor = 0.08;

  if (phase < 0.16) {
    return floor + amplitude * 0.92 * easeOutCubic(phase / 0.16);
  }
  if (phase < 0.34) {
    return floor + amplitude * (0.92 - 0.2 * ((phase - 0.16) / 0.18));
  }
  if (phase < 0.48) {
    return floor + amplitude * (0.72 - 0.33 * ((phase - 0.34) / 0.14));
  }
  if (phase < 0.56) {
    return floor + amplitude * (0.39 - 0.09 * ((phase - 0.48) / 0.08));
  }
  if (phase < 0.68) {
    return floor + amplitude * (0.3 + 0.08 * ((phase - 0.56) / 0.12));
  }
  return floor + amplitude * (0.38 * Math.exp(-2.8 * (phase - 0.68)));
}

function respirationWave(time: number, rr: number, clock: number): number {
  const cycle = 60 / rr;
  const phase = (time % cycle) / cycle;
  const drift = 0.02 * Math.sin(clock * 0.22);
  if (phase < 0.42) {
    return 0.34 + 0.26 * easeInOutSine(phase / 0.42) + drift;
  }
  if (phase < 0.86) {
    return 0.6 - 0.3 * easeInOutSine((phase - 0.42) / 0.44) + drift;
  }
  return 0.3 + 0.04 * ((phase - 0.86) / 0.14) + drift;
}

function smoothPulse(value: number): number {
  return Math.sin(Math.PI * clamp(value, 0, 1));
}

function easeOutCubic(value: number): number {
  const clamped = clamp(value, 0, 1);
  return 1 - Math.pow(1 - clamped, 3);
}

function easeInOutSine(value: number): number {
  const clamped = clamp(value, 0, 1);
  return -(Math.cos(Math.PI * clamped) - 1) / 2;
}

function pointAtX(points: Array<{ x: number; y: number }>, x: number): { x: number; y: number } {
  if (points.length === 0) {
    return { x, y: 0 };
  }
  for (let index = 1; index < points.length; index += 1) {
    if (points[index].x >= x) {
      const previous = points[index - 1];
      const current = points[index];
      const ratio = (x - previous.x) / Math.max(0.0001, current.x - previous.x);
      return {
        x,
        y: previous.y + (current.y - previous.y) * ratio,
      };
    }
  }
  return { x, y: points[points.length - 1].y };
}

function formatLimitSummary(value: AlarmLimitSet): string {
  return `${formatAlarmNumber(value.low)} / ${formatAlarmNumber(value.high)}`;
}

function truncateLabel(value: string, limit: number): string {
  if (value.length <= limit) {
    return value;
  }
  return `${value.slice(0, Math.max(0, limit - 1))}…`;
}

function formatAlarmNumber(value: number): string {
  return Number.isInteger(value) ? `${value}` : value.toFixed(1);
}

function normalizeLimits(value: AlarmLimitSet, fallback: AlarmLimitSet): AlarmLimitSet {
  const low = Number.isFinite(value.low) ? value.low : fallback.low;
  const high = Number.isFinite(value.high) ? value.high : fallback.high;
  return low <= high ? { low, high } : { low: high, high: low };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

const detailLinkStyle: CSSProperties = {
  textDecoration: "none",
  color: "#04121e",
  background: "#d4efff",
  padding: "10px 14px",
  borderRadius: 12,
  fontWeight: 800,
  fontSize: 13,
};

const pillStyle: CSSProperties = {
  padding: "5px 10px",
  borderRadius: 999,
  background: "rgba(22, 48, 74, 0.86)",
  color: "#d4e8ff",
  fontSize: 12,
  fontWeight: 700,
};

const ghostButtonStyle: CSSProperties = {
  border: "1px solid rgba(148, 179, 214, 0.2)",
  background: "rgba(13, 29, 47, 0.88)",
  color: "#d4e8ff",
  borderRadius: 10,
  padding: "8px 10px",
  cursor: "pointer",
};

const editorLabelStyle: CSSProperties = {
  color: "#dbeafe",
  fontSize: 13,
  fontWeight: 700,
  display: "grid",
  gap: 6,
};

const editorInputStyle: CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: "1px solid rgba(148, 179, 214, 0.22)",
  background: "rgba(6, 19, 31, 0.96)",
  color: "#eff7ff",
  padding: "9px 10px",
};
