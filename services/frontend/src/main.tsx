import { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { getNotifications, markNotificationRead } from "./api/http";
import { connectLiveSocket } from "./api/ws";
import { NotificationCenter } from "./components/NotificationCenter";
import { PatientDetailPage } from "./pages/PatientDetail";
import { PatientsPage } from "./pages/Patients";
import type { LiveEvent, NotificationRecord } from "./types/alerts";

const APP_BACKGROUND_SVG = encodeURIComponent(`
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 1000' preserveAspectRatio='xMidYMid slice'>
  <defs>
    <linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='#021126'/>
      <stop offset='45%' stop-color='#032451'/>
      <stop offset='100%' stop-color='#0a4d85'/>
    </linearGradient>
    <radialGradient id='glow' cx='50%' cy='50%' r='50%'>
      <stop offset='0%' stop-color='#8ee8ff' stop-opacity='0.85'/>
      <stop offset='100%' stop-color='#8ee8ff' stop-opacity='0'/>
    </radialGradient>
    <filter id='soft'>
      <feGaussianBlur stdDeviation='10'/>
    </filter>
  </defs>

  <rect width='1600' height='1000' fill='url(#bg)'/>

  <g stroke='#59b6ff' stroke-opacity='0.22' stroke-width='1'>
    <path d='M0 80H1600M0 160H1600M0 240H1600M0 320H1600M0 400H1600M0 480H1600M0 560H1600M0 640H1600M0 720H1600M0 800H1600M0 880H1600'/>
    <path d='M80 0V1000M160 0V1000M240 0V1000M320 0V1000M400 0V1000M480 0V1000M560 0V1000M640 0V1000M720 0V1000M800 0V1000M880 0V1000M960 0V1000M1040 0V1000M1120 0V1000M1200 0V1000M1280 0V1000M1360 0V1000M1440 0V1000M1520 0V1000'/>
  </g>

  <g fill='url(#glow)' opacity='0.8'>
    <circle cx='1270' cy='455' r='230'/>
    <circle cx='260' cy='700' r='160'/>
    <circle cx='1450' cy='260' r='120'/>
  </g>
  <g filter='url(#soft)' opacity='0.35'>
    <circle cx='1270' cy='455' r='80' fill='#c5f8ff'/>
    <circle cx='210' cy='740' r='52' fill='#64deff'/>
    <circle cx='1460' cy='265' r='44' fill='#8ee8ff'/>
  </g>

  <g stroke='#46b2ff' stroke-opacity='0.48' stroke-width='2' fill='none'>
    <path d='M40 350L155 430L240 365L350 290L480 420'/>
    <path d='M200 365L280 300L390 330L520 470'/>
    <path d='M1080 245L1165 365L1290 300L1435 205L1560 418'/>
    <path d='M1120 585L1185 470L1340 595L1520 360'/>
    <path d='M1125 370L1270 455L1430 370'/>
  </g>
  <g fill='#7cdeff' fill-opacity='0.95'>
    <circle cx='40' cy='350' r='7'/>
    <circle cx='155' cy='430' r='7'/>
    <circle cx='240' cy='365' r='7'/>
    <circle cx='280' cy='300' r='7'/>
    <circle cx='390' cy='330' r='7'/>
    <circle cx='480' cy='420' r='7'/>
    <circle cx='1080' cy='245' r='7'/>
    <circle cx='1165' cy='365' r='7'/>
    <circle cx='1270' cy='455' r='8'/>
    <circle cx='1290' cy='300' r='7'/>
    <circle cx='1430' cy='370' r='8'/>
    <circle cx='1435' cy='205' r='8'/>
    <circle cx='1520' cy='360' r='8'/>
    <circle cx='1560' cy='418' r='7'/>
  </g>

  <g opacity='0.75'>
    <circle cx='1120' cy='245' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <circle cx='1290' cy='265' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <circle cx='1415' cy='365' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <circle cx='1385' cy='575' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <circle cx='1280' cy='735' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <circle cx='985' cy='520' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <circle cx='910' cy='410' r='46' fill='rgba(120,193,255,0.32)' stroke='rgba(221,244,255,0.55)' stroke-width='3'/>
    <path d='M1266 249h18M1275 240v18M1371 575h28M1385 561v28' stroke='rgba(255,255,255,0.75)' stroke-width='7' stroke-linecap='round'/>
    <path d='M1088 246c6-18 24-30 45-30c6 0 12 1 17 3' stroke='rgba(255,255,255,0.75)' stroke-width='5' stroke-linecap='round'/>
    <path d='M1147 222c7 0 13 6 13 13s-6 13-13 13s-13-6-13-13s6-13 13-13z' fill='none' stroke='rgba(255,255,255,0.75)' stroke-width='4'/>
    <path d='M954 486h38v56h-38zM964 500h18M964 512h18M964 524h18' stroke='rgba(255,255,255,0.75)' stroke-width='4' stroke-linecap='round'/>
    <path d='M1392 351c10 0 18 7 23 15c5-8 13-15 23-15c16 0 28 13 28 28c0 30-39 51-51 57c-12-6-51-27-51-57c0-15 12-28 28-28z' fill='none' stroke='rgba(255,255,255,0.75)' stroke-width='4'/>
  </g>

  <path d='M0 675L110 675L122 655L135 675L160 675L182 585L205 725L222 675L325 675L372 646L420 675L560 675L602 658L620 675L640 675L660 545L685 725L710 675L790 675L845 648L892 675L990 675L1036 645L1086 675L1600 675'
    fill='none' stroke='#6dff9e' stroke-width='5' stroke-linecap='round' stroke-linejoin='round'/>
  <path d='M0 760C70 700 120 820 180 760S300 690 350 760S470 825 540 760S660 690 735 760S855 810 930 760S1070 690 1135 760S1265 815 1345 760S1495 700 1600 760'
    fill='none' stroke='#5bc6ff' stroke-opacity='0.92' stroke-width='4'/>
  <path d='M0 860C70 848 145 885 225 860S360 835 445 860S585 890 670 860S805 840 890 860S1025 890 1110 860S1245 840 1330 860S1465 885 1600 860'
    fill='none' stroke='#ffd84f' stroke-opacity='0.78' stroke-width='3'/>
</svg>
`);

const APP_BACKGROUND_URL = `url("data:image/svg+xml,${APP_BACKGROUND_SVG}")`;

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
          background: "#041327",
          color: "#0f172a",
          fontFamily: "'Segoe UI', sans-serif",
          position: "relative",
        }}
      >
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 0,
            pointerEvents: "none",
            backgroundImage: APP_BACKGROUND_URL,
            backgroundSize: "cover",
            backgroundPosition: "center",
            backgroundRepeat: "no-repeat",
            opacity: 0.96,
          }}
        />
        <div
          aria-hidden="true"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 0,
            pointerEvents: "none",
            background: "linear-gradient(180deg, rgba(2, 12, 27, 0.18), rgba(2, 12, 27, 0.58))",
          }}
        />
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
        <div style={{ maxWidth: 1240, margin: "0 auto", padding: 24, position: "relative", zIndex: 1 }}>
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
