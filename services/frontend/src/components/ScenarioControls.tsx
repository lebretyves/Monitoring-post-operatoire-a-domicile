type HypothesisCompatibility = "high" | "medium" | "low";
type TruthStatus = "match" | "mismatch" | "unknown";
type VerdictTone = "positive" | "negative" | "warning" | "neutral";

interface ScenarioHypothesisSnapshot {
  label: string;
  percent: number;
  compatibility: HypothesisCompatibility;
  truthStatus: TruthStatus;
}

interface ScenarioValidationVerdict {
  label: string;
  detail: string;
  tone: VerdictTone;
}

interface ScenarioControlsProps {
  scenario: string;
  revealed: boolean;
  canReveal: boolean;
  onReveal: () => void;
  beforeHypothesis: ScenarioHypothesisSnapshot | null;
  afterHypothesis: ScenarioHypothesisSnapshot | null;
  verdict: ScenarioValidationVerdict | null;
  helperText: string;
}

export function ScenarioControls({
  scenario,
  revealed,
  canReveal,
  onReveal,
  beforeHypothesis,
  afterHypothesis,
  verdict,
  helperText,
}: ScenarioControlsProps) {
  return (
    <div
      style={{
        borderRadius: 16,
        padding: 16,
        border: "1px solid #dbeafe",
        background: "linear-gradient(180deg, #f8fbff 0%, #eff6ff 100%)",
        display: "grid",
        gap: 14,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ display: "grid", gap: 4 }}>
          <div style={{ fontWeight: 800, color: "#0f172a" }}>Validation en aveugle</div>
          <div style={{ color: "#475569", fontSize: 14 }}>
            Compare l'orientation initiale puis, si disponible, la reevaluation apres questionnaire avant de reveler la verite terrain.
          </div>
        </div>
        <button
          type="button"
          onClick={onReveal}
          disabled={!canReveal || revealed}
          style={{
            border: 0,
            cursor: !canReveal || revealed ? "not-allowed" : "pointer",
            background: !canReveal ? "#cbd5e1" : revealed ? "#0f172a" : "#0f766e",
            color: "#ffffff",
            padding: "10px 14px",
            borderRadius: 10,
            fontWeight: 700,
            opacity: !canReveal || revealed ? 0.75 : 1,
          }}
        >
          {!canReveal ? "Analyse initiale requise" : revealed ? "Verite terrain revelee" : "Reveler la verite terrain"}
        </button>
      </div>

      <div
        style={{
          borderRadius: 14,
          padding: 14,
          border: "1px dashed #93c5fd",
          background: revealed ? "#ffffff" : "rgba(15, 23, 42, 0.04)",
          display: "grid",
          gap: 6,
        }}
      >
        <div style={{ color: "#64748b", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Verite terrain
        </div>
        <div style={{ color: "#0f172a", fontWeight: 800, fontSize: 18 }}>
          {revealed ? scenario || "Scenario non renseigne" : "Scenario reel masque jusqu'a revelation"}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        <HypothesisCard title="Avant questionnaire" snapshot={beforeHypothesis} revealed={revealed} />
        <HypothesisCard
          title="Apres questionnaire"
          snapshot={afterHypothesis}
          revealed={revealed}
          emptyText="Aucun questionnaire declenche pour ce cas."
        />
      </div>

      <div style={{ color: "#475569", fontSize: 14 }}>{helperText}</div>

      {verdict ? (
        <div
          style={{
            borderRadius: 14,
            padding: 14,
            border: `1px solid ${verdictBorderColor(verdict.tone)}`,
            background: verdictTint(verdict.tone),
            display: "grid",
            gap: 4,
          }}
        >
          <div style={{ color: verdictTextColor(verdict.tone), fontWeight: 800 }}>{verdict.label}</div>
          <div style={{ color: "#334155", fontSize: 14 }}>{verdict.detail}</div>
        </div>
      ) : null}
    </div>
  );
}

function HypothesisCard({
  title,
  snapshot,
  revealed,
  emptyText = "Evaluation indisponible pour le moment.",
}: {
  title: string;
  snapshot: ScenarioHypothesisSnapshot | null;
  revealed: boolean;
  emptyText?: string;
}) {
  return (
    <div style={{ borderRadius: 14, padding: 14, border: "1px solid #dbeafe", background: "#ffffff", display: "grid", gap: 8 }}>
      <div style={{ color: "#64748b", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        {title}
      </div>
      {snapshot ? (
        <>
          <div style={{ color: "#0f172a", fontWeight: 800 }}>{snapshot.label}</div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ color: compatibilityColor(snapshot.compatibility), fontWeight: 700 }}>
              {formatCompatibility(snapshot.compatibility)}
            </div>
            <div style={{ color: "#0f172a", fontWeight: 800 }}>{snapshot.percent}%</div>
          </div>
          {revealed ? (
            <div
              style={{
                width: "fit-content",
                borderRadius: 999,
                padding: "6px 10px",
                background: truthTint(snapshot.truthStatus),
                color: truthColor(snapshot.truthStatus),
                fontSize: 12,
                fontWeight: 800,
              }}
            >
              {formatTruthStatus(snapshot.truthStatus)}
            </div>
          ) : null}
        </>
      ) : (
        <div style={{ color: "#64748b", fontSize: 14 }}>
          {emptyText}
        </div>
      )}
    </div>
  );
}

function formatCompatibility(level: HypothesisCompatibility): string {
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

function compatibilityColor(level: HypothesisCompatibility): string {
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

function formatTruthStatus(status: TruthStatus): string {
  switch (status) {
    case "match":
      return "Concordant avec la verite terrain";
    case "mismatch":
      return "Non concordant";
    default:
      return "Correspondance non interpretable";
  }
}

function truthTint(status: TruthStatus): string {
  switch (status) {
    case "match":
      return "#dcfce7";
    case "mismatch":
      return "#fee2e2";
    default:
      return "#e2e8f0";
  }
}

function truthColor(status: TruthStatus): string {
  switch (status) {
    case "match":
      return "#166534";
    case "mismatch":
      return "#b91c1c";
    default:
      return "#475569";
  }
}

function verdictTint(tone: VerdictTone): string {
  switch (tone) {
    case "positive":
      return "#dcfce7";
    case "negative":
      return "#fee2e2";
    case "warning":
      return "#ffedd5";
    default:
      return "#f8fafc";
  }
}

function verdictTextColor(tone: VerdictTone): string {
  switch (tone) {
    case "positive":
      return "#166534";
    case "negative":
      return "#b91c1c";
    case "warning":
      return "#c2410c";
    default:
      return "#0f172a";
  }
}

function verdictBorderColor(tone: VerdictTone): string {
  switch (tone) {
    case "positive":
      return "#86efac";
    case "negative":
      return "#fca5a5";
    case "warning":
      return "#fdba74";
    default:
      return "#cbd5e1";
  }
}
