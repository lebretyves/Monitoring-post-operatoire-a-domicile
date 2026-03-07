import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { PatientDetailPage } from "./pages/PatientDetail";
import { PatientsPage } from "./pages/Patients";

function AppShell() {
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

ReactDOM.createRoot(document.getElementById("root")!).render(<AppShell />);
