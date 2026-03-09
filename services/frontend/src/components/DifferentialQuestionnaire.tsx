import type {
  QuestionnaireModule,
  QuestionnaireSubmission
} from "../types/vitals";

interface DifferentialQuestionnaireProps {
  modules: QuestionnaireModule[];
  triggerSummary: string[];
  value: QuestionnaireSubmission;
  onChange: (next: QuestionnaireSubmission) => void;
  onSubmit: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  restState?: "active" | "resting" | "stale";
  restMessage?: string;
  loading?: boolean;
}

export function DifferentialQuestionnaire({
  modules,
  triggerSummary,
  value,
  onChange,
  onSubmit,
  collapsed = true,
  onToggleCollapsed,
  restState = "active",
  restMessage = "",
  loading = false,
}: DifferentialQuestionnaireProps) {
  if (modules.length === 0) {
    return null;
  }

  const answeredCount = value.answers.length;

  return (
    <section style={panelStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ display: "grid", gap: 6 }}>
          <h3 style={{ margin: 0 }}>Questions differentielles</h3>
          <div style={{ color: "#64748b", fontSize: 14 }}>
            Ces questions s'ouvrent a partir des premieres alertes pour affiner l'analyse clinique.
          </div>
          {restState !== "active" ? (
            <div style={{ color: restState === "stale" ? "#b91c1c" : "#0f766e", fontSize: 13, fontWeight: 700 }}>
              {restMessage}
            </div>
          ) : null}
          {collapsed ? (
            <div style={{ color: "#475569", fontSize: 13 }}>
              {answeredCount > 0
                ? `${answeredCount} reponse${answeredCount > 1 ? "s" : ""} conservee${answeredCount > 1 ? "s" : ""} pour la reevaluation.`
                : "Questionnaire replie pour liberer la vue."}
            </div>
          ) : null}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {restState !== "active" ? (
            <span
              style={{
                borderRadius: 999,
                padding: "6px 10px",
                background: restState === "stale" ? "#fee2e2" : "#dcfce7",
                color: restState === "stale" ? "#b91c1c" : "#166534",
                fontSize: 12,
                fontWeight: 800,
              }}
            >
              {restState === "stale" ? "Reevaluation conseillee" : "Analyse au repos"}
            </span>
          ) : null}
          {onToggleCollapsed ? (
            <button
              type="button"
              onClick={onToggleCollapsed}
              style={toggleButtonStyle}
            >
              {collapsed ? "Ouvrir" : "Refermer"}
            </button>
          ) : null}
        </div>
      </div>

      {collapsed ? (
        <>
          {triggerSummary.length > 0 ? (
            <div style={{ color: "#475569", fontSize: 13 }}>
              Declencheurs: {triggerSummary.join(" | ")}
            </div>
          ) : null}
          {value.comment.trim() ? (
            <div style={{ color: "#475569", fontSize: 13 }}>
              Commentaire conserve: {value.comment.trim()}
            </div>
          ) : null}
        </>
      ) : (
        <>
          {triggerSummary.length > 0 ? (
            <div style={{ color: "#475569", fontSize: 13 }}>
              Declencheurs: {triggerSummary.join(" | ")}
            </div>
          ) : null}

          <label style={fieldLabel}>
            Reponses recueillies par
            <select
              value={value.responder}
              onChange={(event) => onChange({ ...value, responder: event.target.value })}
              style={selectStyle}
            >
              <option value="patient">Patient</option>
              <option value="proche">Proche</option>
              <option value="ide">IDE</option>
            </select>
          </label>

          <div style={{ display: "grid", gap: 12 }}>
            {modules.map((module) => (
              <div key={module.id} style={moduleCard}>
                <div style={{ display: "grid", gap: 4 }}>
                  <div style={{ fontWeight: 700, color: "#0f172a" }}>{module.title}</div>
                  <div style={{ color: "#475569", fontSize: 14 }}>{module.description}</div>
                  <div style={{ color: "#64748b", fontSize: 13 }}>
                    Cibles: {module.targets.join(", ")}
                  </div>
                </div>

                <div style={{ display: "grid", gap: 10 }}>
                  {module.questions.map((question) => {
                    const currentAnswer =
                      value.answers.find(
                        (row) => row.module_id === module.id && row.question_id === question.id
                      )?.answer ?? "";
                    return (
                      <label key={question.id} style={fieldLabel}>
                        {question.label}
                        <select
                          value={currentAnswer}
                          onChange={(event) =>
                            onChange({
                              ...value,
                              answers: upsertAnswer(value.answers, {
                                module_id: module.id,
                                question_id: question.id,
                                answer: event.target.value,
                              }),
                            })
                          }
                          style={selectStyle}
                        >
                          <option value="">Selectionner</option>
                          {question.options.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    );
                  })}
                </div>

                {module.source_refs.length > 0 ? (
                  <div style={{ color: "#64748b", fontSize: 12, display: "grid", gap: 4 }}>
                    {module.source_refs.map((source) => (
                      <div key={`${module.id}-${source.url}`}>
                        Source: <a href={source.url} target="_blank" rel="noreferrer" style={{ color: "#0f766e" }}>{source.label}</a>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          <label style={fieldLabel}>
            Commentaire libre
            <textarea
              value={value.comment}
              onChange={(event) => onChange({ ...value, comment: event.target.value })}
              rows={3}
              style={{ ...selectStyle, resize: "vertical", minHeight: 84 }}
              placeholder="Ex: essoufflement brutal a la marche, douleur pleurale a droite..."
            />
          </label>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={onSubmit}
              disabled={loading}
              style={{
                border: 0,
                cursor: "pointer",
                background: "#0f172a",
                color: "#ffffff",
                padding: "10px 14px",
                borderRadius: 10,
              }}
            >
              {loading ? "Reanalyse..." : "Reanalyser avec les reponses"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function upsertAnswer(
  answers: QuestionnaireSubmission["answers"],
  nextAnswer: QuestionnaireSubmission["answers"][number]
): QuestionnaireSubmission["answers"] {
  const filtered = answers.filter(
    (row) => !(row.module_id === nextAnswer.module_id && row.question_id === nextAnswer.question_id)
  );
  if (!nextAnswer.answer) {
    return filtered;
  }
  return [...filtered, nextAnswer];
}

const panelStyle = {
  background: "#ffffff",
  borderRadius: 18,
  padding: 18,
  boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)",
  display: "grid",
  gap: 16,
} as const;

const moduleCard = {
  borderRadius: 14,
  background: "#f8fafc",
  padding: 14,
  border: "1px solid #e2e8f0",
  display: "grid",
  gap: 12,
} as const;

const fieldLabel = {
  display: "grid",
  gap: 6,
  color: "#334155",
  fontWeight: 600,
} as const;

const selectStyle = {
  width: "100%",
  border: "1px solid #cbd5e1",
  borderRadius: 12,
  padding: "12px 14px",
  font: "inherit",
  color: "#0f172a",
  background: "#ffffff",
} as const;

const toggleButtonStyle = {
  border: 0,
  cursor: "pointer",
  background: "#dbeafe",
  color: "#0f172a",
  padding: "10px 14px",
  borderRadius: 10,
  fontWeight: 700,
} as const;
