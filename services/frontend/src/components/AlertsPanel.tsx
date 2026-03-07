import type { AlertRecord } from "../types/alerts";

interface AlertsPanelProps {
  alerts: AlertRecord[];
  onAck?: (alertId: number) => Promise<void> | void;
  title?: string;
}

const colors: Record<string, string> = {
  INFO: "#2563eb",
  WARNING: "#d97706",
  CRITICAL: "#dc2626"
};

function metricText(snapshot: Record<string, unknown>, key: string): string | null {
  const value = snapshot[key];
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number") {
    return `${value}`;
  }
  return null;
}

function metricList(snapshot: Record<string, unknown>, key: string): string[] {
  const value = snapshot[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item)).filter(Boolean);
}

export function AlertsPanel({ alerts, onAck, title = "Alertes" }: AlertsPanelProps) {
  return (
    <div style={{ background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <div style={{ display: "grid", gap: 12 }}>
        {alerts.length === 0 && <div style={{ color: "#64748b" }}>Aucune alerte pour le moment.</div>}
        {alerts.map((alert) => (
          <div key={alert.id} style={{ border: "1px solid #e2e8f0", borderRadius: 14, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <strong>{alert.title}</strong>
              <span style={{ color: "#ffffff", background: colors[alert.level] ?? "#334155", padding: "4px 8px", borderRadius: 999 }}>
                {alert.level}
              </span>
            </div>
            <div style={{ marginTop: 8, color: "#334155" }}>{alert.message}</div>
            {metricText(alert.metric_snapshot, "suspicion_stage") && (
              <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 8 }}>
                <span style={{ background: "#eff6ff", color: "#1d4ed8", padding: "4px 8px", borderRadius: 999, fontSize: 12 }}>
                  {metricText(alert.metric_snapshot, "suspicion_stage")?.replaceAll("_", " ")}
                </span>
                <span style={{ background: "#f8fafc", color: "#334155", padding: "4px 8px", borderRadius: 999, fontSize: 12 }}>
                  confiance {metricText(alert.metric_snapshot, "confidence_score")}/100
                </span>
                <span style={{ background: "#fff7ed", color: "#c2410c", padding: "4px 8px", borderRadius: 999, fontSize: 12 }}>
                  FP {metricText(alert.metric_snapshot, "false_positive_risk")}
                </span>
                <span style={{ background: "#fef2f2", color: "#b91c1c", padding: "4px 8px", borderRadius: 999, fontSize: 12 }}>
                  FN {metricText(alert.metric_snapshot, "false_negative_risk")}
                </span>
                {metricText(alert.metric_snapshot, "remeasure_minutes") !== "0" && (
                  <span style={{ background: "#f0fdf4", color: "#166534", padding: "4px 8px", borderRadius: 999, fontSize: 12 }}>
                    recontrole {metricText(alert.metric_snapshot, "remeasure_minutes")} min
                  </span>
                )}
              </div>
            )}
            {metricText(alert.metric_snapshot, "uncertainty_note") && (
              <div style={{ marginTop: 8, fontSize: 13, color: "#475569" }}>
                {metricText(alert.metric_snapshot, "uncertainty_note")}
              </div>
            )}
            {(metricList(alert.metric_snapshot, "false_positive_examples").length > 0 ||
              metricList(alert.metric_snapshot, "false_negative_examples").length > 0) && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#64748b", display: "grid", gap: 4 }}>
                {metricList(alert.metric_snapshot, "false_positive_examples").length > 0 && (
                  <div>FP possibles: {metricList(alert.metric_snapshot, "false_positive_examples").join(", ")}</div>
                )}
                {metricList(alert.metric_snapshot, "false_negative_examples").length > 0 && (
                  <div>FN possibles: {metricList(alert.metric_snapshot, "false_negative_examples").join(", ")}</div>
                )}
              </div>
            )}
            <div style={{ marginTop: 8, fontSize: 13, color: "#64748b" }}>
              {new Date(alert.created_at).toLocaleString()} - statut {alert.status}
            </div>
            {onAck && alert.status !== "ACKNOWLEDGED" && (
              <button
                type="button"
                onClick={() => onAck(alert.id)}
                style={{ marginTop: 10, border: 0, background: "#0f172a", color: "#ffffff", padding: "8px 12px", borderRadius: 10, cursor: "pointer" }}
              >
                Marquer comme vue
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
