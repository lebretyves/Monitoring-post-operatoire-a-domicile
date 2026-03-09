import type { CSSProperties } from "react";

import type { NotificationRecord } from "../types/alerts";

export function NotificationCenter({
  notifications,
  onMarkRead,
  browserPermission,
  onRequestBrowserPermission,
  compact = false,
}: {
  notifications: NotificationRecord[];
  onMarkRead: (notificationId: number) => Promise<void> | void;
  browserPermission: NotificationPermission | "unsupported";
  onRequestBrowserPermission: () => Promise<void> | void;
  compact?: boolean;
}) {
  const unreadCount = notifications.filter((item) => item.status === "UNREAD").length;
  const permissionLabel =
    browserPermission === "granted"
      ? "Notifications navigateur actives"
      : browserPermission === "denied"
        ? "Notifications navigateur bloquees"
        : browserPermission === "unsupported"
          ? "Notifications navigateur indisponibles"
          : "Activer les notifications navigateur";

  return (
    <section
      style={{
        background: "#ffffff",
        borderRadius: compact ? 16 : 20,
        padding: compact ? 14 : 18,
        boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)",
        display: "grid",
        gap: 14,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 13, color: "#64748b", fontWeight: 700 }}>Notifications</div>
          <div style={{ fontSize: 15, fontWeight: 800, color: "#0f172a" }}>
            {unreadCount > 0 ? `${unreadCount} non lue${unreadCount > 1 ? "s" : ""}` : "Aucune notification non lue"}
          </div>
        </div>
        <button
          type="button"
          onClick={() => onRequestBrowserPermission()}
          disabled={browserPermission === "granted" || browserPermission === "unsupported"}
          style={{
            border: 0,
            cursor:
              browserPermission === "granted" || browserPermission === "unsupported" ? "default" : "pointer",
            background: browserPermission === "granted" ? "#dcfce7" : "#dbeafe",
            color: "#0f172a",
            padding: "10px 14px",
            borderRadius: 10,
            fontWeight: 700,
          }}
        >
          {permissionLabel}
        </button>
      </div>

      {notifications.length === 0 ? (
        <div style={{ color: "#64748b", fontSize: 14 }}>Aucune notification generee pour le moment.</div>
      ) : (
        <div style={{ display: "grid", gap: 10, maxHeight: compact ? 320 : 420, overflowY: "auto", paddingRight: 4 }}>
          {notifications.map((notification) => (
            <article
              key={notification.id}
              style={{
                borderRadius: 14,
                background: notification.status === "UNREAD" ? "#f8fafc" : "#ffffff",
                border: `1px solid ${levelBorder(notification.level)}`,
                borderLeft: `6px solid ${levelAccent(notification.level)}`,
                padding: 14,
                display: "grid",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <div style={{ fontWeight: 800, color: "#0f172a" }}>{notification.title}</div>
                <div style={{ color: levelAccent(notification.level), fontWeight: 800, fontSize: 13 }}>
                  {notification.level}
                </div>
              </div>
              <div style={{ color: "#334155", fontSize: 14 }}>{notification.message}</div>
              <div style={{ color: "#64748b", fontSize: 13 }}>
                {notification.patient_id} - {formatNotificationDate(notification.created_at)}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <span style={notification.status === "UNREAD" ? unreadBadge : readBadge}>
                  {notification.status === "UNREAD" ? "Non lue" : "Vue"}
                </span>
                {notification.status === "UNREAD" ? (
                  <button type="button" onClick={() => onMarkRead(notification.id)} style={markReadButton}>
                    Marquer comme vue
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function levelAccent(level: NotificationRecord["level"]): string {
  switch (level) {
    case "CRITICAL":
      return "#b91c1c";
    case "WARNING":
      return "#c2410c";
    case "INFO":
      return "#0f766e";
    default:
      return "#475569";
  }
}

function levelBorder(level: NotificationRecord["level"]): string {
  switch (level) {
    case "CRITICAL":
      return "#fecaca";
    case "WARNING":
      return "#fed7aa";
    case "INFO":
      return "#bbf7d0";
    default:
      return "#e2e8f0";
  }
}

function formatNotificationDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const unreadBadge: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  borderRadius: 999,
  background: "#dbeafe",
  color: "#0f172a",
  fontSize: 12,
  fontWeight: 700,
  padding: "4px 10px",
};

const readBadge: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  borderRadius: 999,
  background: "#e2e8f0",
  color: "#475569",
  fontSize: 12,
  fontWeight: 700,
  padding: "4px 10px",
};

const markReadButton: CSSProperties = {
  border: 0,
  cursor: "pointer",
  background: "#0f172a",
  color: "#ffffff",
  padding: "8px 12px",
  borderRadius: 10,
  fontWeight: 700,
};
