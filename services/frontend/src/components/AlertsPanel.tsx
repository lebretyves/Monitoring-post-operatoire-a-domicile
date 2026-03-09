import { useEffect, useState } from "react";

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
  const [openAlertIds, setOpenAlertIds] = useState<number[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    setOpenAlertIds((current) => current.filter((id) => alerts.some((alert) => alert.id === id)));
  }, [alerts]);

  return (
    <div style={{ background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
      <button
        type="button"
        onClick={() => setPanelOpen((current) => !current)}
        style={{
          width: "100%",
          border: 0,
          background: "transparent",
          padding: 0,
          cursor: "pointer",
          display: "flex",
          justifyContent: "space-between",
          gap: 12,
          alignItems: "center",
          textAlign: "left",
        }}
      >
        <div style={{ display: "grid", gap: 4 }}>
          <h3 style={{ margin: 0 }}>{title}</h3>
          <div style={{ color: "#64748b", fontSize: 13 }}>
            {alerts.length === 0
              ? "Aucune alerte pour le moment."
              : `${alerts.length} alerte${alerts.length > 1 ? "s" : ""} ${panelOpen ? "affichee" : "masquee"}${alerts.length > 1 ? "s" : ""}`}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {alerts.length > 0 ? (
            <span
              style={{
                minWidth: 28,
                height: 28,
                padding: "0 10px",
                borderRadius: 999,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                background: "#e2e8f0",
                color: "#0f172a",
                fontWeight: 800,
                fontSize: 12,
              }}
            >
              {alerts.length}
            </span>
          ) : null}
          <span style={{ color: "#475569", fontSize: 18, lineHeight: 1 }}>
            {panelOpen ? "−" : "+"}
          </span>
        </div>
      </button>
      {panelOpen ? (
        <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
          {alerts.map((alert) => (
          <details
            key={alert.id}
            open={openAlertIds.includes(alert.id)}
            onToggle={(event) => {
              const isOpen = (event.currentTarget as HTMLDetailsElement).open;
              setOpenAlertIds((current) =>
                isOpen ? Array.from(new Set([...current, alert.id])) : current.filter((id) => id !== alert.id)
              );
            }}
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: 14,
              background: "#ffffff",
              overflow: "hidden",
            }}
          >
            <summary
              style={{
                listStyle: "none",
                cursor: "pointer",
                padding: 12,
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", minWidth: 0 }}>
                  <strong style={{ minWidth: 0 }}>{alert.title}</strong>
                  {alert.metric_snapshot.historical_backfill === true && (
                    <span style={{ background: "#e2e8f0", color: "#334155", padding: "4px 8px", borderRadius: 999, fontSize: 12 }}>
                      Historique
                    </span>
                  )}
                </div>
                <span style={{ color: "#ffffff", background: colors[alert.level] ?? "#334155", padding: "4px 8px", borderRadius: 999, whiteSpace: "nowrap" }}>
                  {alert.level}
                </span>
              </div>
              <div style={{ color: "#475569", fontSize: 14 }}>
                {alert.message}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", fontSize: 12, color: "#64748b" }}>
                <span>{new Date(alert.created_at).toLocaleString()}</span>
                <span>statut {alert.status}</span>
              </div>
            </summary>

            <div style={{ padding: "0 12px 12px", display: "grid", gap: 8 }}>
              {metricText(alert.metric_snapshot, "suspicion_stage") && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
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
                <div style={{ fontSize: 13, color: "#475569" }}>
                  {metricText(alert.metric_snapshot, "uncertainty_note")}
                </div>
              )}
              {(metricList(alert.metric_snapshot, "false_positive_examples").length > 0 ||
                metricList(alert.metric_snapshot, "false_negative_examples").length > 0) && (
                <div style={{ fontSize: 12, color: "#64748b", display: "grid", gap: 4 }}>
                  {metricList(alert.metric_snapshot, "false_positive_examples").length > 0 && (
                    <div>FP possibles: {metricList(alert.metric_snapshot, "false_positive_examples").join(", ")}</div>
                  )}
                  {metricList(alert.metric_snapshot, "false_negative_examples").length > 0 && (
                    <div>FN possibles: {metricList(alert.metric_snapshot, "false_negative_examples").join(", ")}</div>
                  )}
                </div>
              )}
              {onAck && alert.status !== "ACKNOWLEDGED" && (
                <button
                  type="button"
                  onClick={() => onAck(alert.id)}
                  style={{ justifySelf: "start", border: 0, background: "#0f172a", color: "#ffffff", padding: "8px 12px", borderRadius: 10, cursor: "pointer" }}
                >
                  Marquer comme vue
                </button>
              )}
            </div>
          </details>
          ))}
        </div>
      ) : null}
    </div>
  );
}
