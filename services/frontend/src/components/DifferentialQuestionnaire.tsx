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
  loading?: boolean;
}

export function DifferentialQuestionnaire({
  modules,
  triggerSummary,
  value,
  onChange,
  onSubmit,
  loading = false,
}: DifferentialQuestionnaireProps) {
  if (modules.length === 0) {
    return null;
  }

  return (
    <section style={panelStyle}>
      <div style={{ display: "grid", gap: 6 }}>
        <h3 style={{ margin: 0 }}>Questions differentielles</h3>
        <div style={{ color: "#64748b", fontSize: 14 }}>
          Ces questions s'ouvrent a partir des premieres alertes pour affiner l'analyse clinique.
        </div>
        {triggerSummary.length > 0 && (
          <div style={{ color: "#475569", fontSize: 13 }}>
            Declencheurs: {triggerSummary.join(" | ")}
          </div>
        )}
      </div>

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

            {module.source_refs.length > 0 && (
              <div style={{ color: "#64748b", fontSize: 12, display: "grid", gap: 4 }}>
                {module.source_refs.map((source) => (
                  <div key={`${module.id}-${source.url}`}>
                    Source: <a href={source.url} target="_blank" rel="noreferrer" style={{ color: "#0f766e" }}>{source.label}</a>
                  </div>
                ))}
              </div>
            )}
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
