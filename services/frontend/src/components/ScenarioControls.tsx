interface ScenarioControlsProps {
  scenario: string;
}

export function ScenarioControls({ scenario }: ScenarioControlsProps) {
  return (
    <div style={{ background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
      <h3 style={{ marginTop: 0 }}>Contexte clinique</h3>
      <div style={{ marginBottom: 10 }}>
        Scenario courant <strong>{scenario}</strong>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <span
          style={{
            border: "1px solid #cbd5e1",
            background: "#f8fafc",
            color: "#0f172a",
            padding: "8px 12px",
            borderRadius: 999,
            fontWeight: 700,
          }}
        >
          Lecture seule
        </span>
        <span
          style={{
            border: "1px solid #bfdbfe",
            background: "#eff6ff",
            color: "#1d4ed8",
            padding: "8px 12px",
            borderRadius: 999,
            fontWeight: 700,
          }}
        >
          Cas actif
        </span>
      </div>
      <p style={{ marginBottom: 0, marginTop: 12, color: "#64748b" }}>
        Ce panneau est informatif uniquement. Les alertes et validations affichent la combinaison pathologie + chirurgie active.
      </p>
    </div>
  );
}
