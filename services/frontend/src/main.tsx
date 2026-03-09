import { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { getNotifications, markNotificationRead } from "./api/http";
import { connectLiveSocket } from "./api/ws";
import { NotificationCenter } from "./components/NotificationCenter";
import { PatientDetailPage } from "./pages/PatientDetail";
import { PatientsPage } from "./pages/Patients";
import type { LiveEvent, NotificationRecord } from "./types/alerts";

function AppShell() {
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [browserPermission, setBrowserPermission] = useState<NotificationPermission | "unsupported">(
    readBrowserPermission()
  );
  const [open, setOpen] = useState(false);
  const unreadCount = notifications.filter((item) => item.status === "UNREAD").length;

  useEffect(() => {
    getNotifications().then((rows) => {
      setNotifications(rows.slice(0, 20));
    }).catch(console.error);

    const cleanup = connectLiveSocket((event: LiveEvent) => {
      if (event.type === "notification") {
        const notification = event.payload as NotificationRecord;
        setNotifications((current) => [notification, ...current.filter((item) => item.id !== notification.id)].slice(0, 20));
        showBrowserNotification(notification);
      }
      if (event.type === "notifications_reset") {
        setNotifications([]);
        getNotifications().then((rows) => {
          setNotifications(rows.slice(0, 20));
        }).catch(console.error);
      }
      if (event.type === "notification_read") {
        const notification = event.payload as NotificationRecord;
        setNotifications((current) => current.map((item) => (item.id === notification.id ? notification : item)));
      }
    });

    return cleanup;
  }, []);

  return (
    <BrowserRouter>
      <div
        style={{
          minHeight: "100vh",
          background: "radial-gradient(circle at top left, #d9f99d, #e2e8f0 38%, #f8fafc 100%)",
          color: "#0f172a",
          fontFamily: "'Segoe UI', sans-serif"
        }}
      >
        <div
          style={{
            position: "fixed",
            top: 18,
            right: 18,
            zIndex: 60,
            width: open ? 380 : "auto",
            display: "grid",
            gap: 10,
            justifyItems: "end",
          }}
        >
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            style={{
              border: 0,
              cursor: "pointer",
              background: "#0f172a",
              color: "#ffffff",
              borderRadius: 999,
              padding: "12px 16px",
              fontWeight: 800,
              boxShadow: "0 12px 24px rgba(15, 23, 42, 0.2)",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <span>Notifications</span>
            <span
              style={{
                minWidth: 26,
                height: 26,
                borderRadius: 999,
                background: unreadCount > 0 ? "#facc15" : "#334155",
                color: "#0f172a",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 12,
                fontWeight: 900,
                padding: "0 6px",
              }}
            >
              {unreadCount}
            </span>
          </button>
          {open ? (
            <div style={{ width: 380 }}>
              <NotificationCenter
                notifications={notifications}
                onMarkRead={async (notificationId) => {
                  const updated = await markNotificationRead(notificationId);
                  setNotifications((current) => current.map((item) => (item.id === updated.id ? updated : item)));
                }}
                browserPermission={browserPermission}
                onRequestBrowserPermission={async () => {
                  if (!("Notification" in window)) {
                    setBrowserPermission("unsupported");
                    return;
                  }
                  const permission = await window.Notification.requestPermission();
                  setBrowserPermission(permission);
                }}
              />
            </div>
          ) : null}
        </div>
        <div style={{ maxWidth: 1240, margin: "0 auto", padding: 24 }}>
          <Routes>
            <Route path="/" element={<PatientsPage />} />
            <Route path="/patients/:patientId" element={<PatientDetailPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

function readBrowserPermission(): NotificationPermission | "unsupported" {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "unsupported";
  }
  return window.Notification.permission;
}

function showBrowserNotification(notification: NotificationRecord): void {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return;
  }
  if (window.Notification.permission !== "granted") {
    return;
  }
  new window.Notification(notification.title, {
    body: `${notification.patient_id} - ${notification.message}`,
    tag: `postop-${notification.id}`,
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(<AppShell />);
