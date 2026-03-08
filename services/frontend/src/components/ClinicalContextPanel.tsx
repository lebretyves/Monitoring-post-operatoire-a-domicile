import { useEffect, useRef, useState } from "react";

import type { ClinicalContextSelection } from "../types/vitals";

const PATIENT_FACTORS = [
  "Age > 70 ans",
  "Diabete",
  "Obesite",
  "BPCO / asthme",
  "Tabagisme actif ou ancien",
  "Anemie",
  "Insuffisance renale",
  "Anticoagulation",
  "Antecedent TVP / EP",
  "Coronaropathie / insuffisance cardiaque",
  "Immunodepression / corticoides",
  "Douleur chronique / opioides",
  "Anxiete / facteurs psychiques",
  "SAOS",
  "Autre (preciser dans le commentaire)",
];

const PERIOPERATIVE_CONTEXT = [
  "ASA >= 3",
  "Chirurgie urgente",
  "Duree operatoire prolongee",
  "Immobilite prolongee",
  "Infection recente",
  "Ventilation prolongee",
  "Denutrition / hypoalbuminemie",
  "Autre (preciser dans le commentaire)",
];

const COMPLICATIONS_TO_DISCUSS = [
  "Sepsis",
  "Embolie pulmonaire",
  "Pneumopathie / IRA",
  "Hemorragie post-op",
  "Douleur post-op",
  "Complication cardiaque post-op",
  "Autre (preciser dans le commentaire)",
];

interface ClinicalContextPanelProps {
  value: ClinicalContextSelection;
  onChange: (next: ClinicalContextSelection) => void;
  onAnalyze: () => void;
  loading: boolean;
}

export function ClinicalContextPanel({
  value,
  onChange,
  onAnalyze,
  loading,
}: ClinicalContextPanelProps) {
  return (
    <div
      style={{
        background: "#ffffff",
        borderRadius: 18,
        padding: 16,
        boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)",
        display: "grid",
        gap: 14,
      }}
    >
      <div>
        <h3 style={{ marginTop: 0, marginBottom: 6 }}>Contexte patient</h3>
        <div style={{ color: "#64748b", fontSize: 14 }}>
          Ces elements enrichissent uniquement l'analyse IA. Ils ne modifient ni le simulateur, ni les alertes, ni les constantes.
        </div>
      </div>

      <ContextDropdown
        title="Terrain patient"
        options={PATIENT_FACTORS}
        selected={value.patient_factors}
        onChange={(items) => onChange({ ...value, patient_factors: items })}
      />

      <ContextDropdown
        title="Contexte peri-op"
        options={PERIOPERATIVE_CONTEXT}
        selected={value.perioperative_context}
        onChange={(items) => onChange({ ...value, perioperative_context: items })}
      />

      <ContextDropdown
        title="Complications a discuter"
        options={COMPLICATIONS_TO_DISCUSS}
        selected={value.complications_to_discuss}
        onChange={(items) => onChange({ ...value, complications_to_discuss: items })}
      />

      <label style={{ display: "grid", gap: 6, color: "#334155", fontWeight: 600 }}>
        Commentaire libre
        <textarea
          value={value.free_text}
          onChange={(event) => onChange({ ...value, free_text: event.target.value })}
          placeholder="Precise ici les elements choisis comme 'Autre' ou tout contexte clinique additionnel."
          rows={3}
          style={{
            width: "100%",
            borderRadius: 12,
            border: "1px solid #cbd5e1",
            padding: 10,
            font: "inherit",
            resize: "vertical",
            minHeight: 80,
          }}
        />
      </label>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 10,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <div style={{ color: "#64748b", fontSize: 13 }}>
          Clique sur une liste pour l'ouvrir. Chaque choix est visible juste dessous et tu peux supprimer un item individuellement.
        </div>
        <button
          type="button"
          onClick={onAnalyze}
          disabled={loading}
          style={{
            border: "none",
            borderRadius: 999,
            padding: "10px 16px",
            background: "#0f172a",
            color: "#ffffff",
            fontWeight: 700,
            cursor: loading ? "wait" : "pointer",
          }}
        >
          {loading ? "Analyse IA..." : "Analyser avec contexte patient"}
        </button>
      </div>
    </div>
  );
}

function ContextDropdown({
  title,
  options,
  selected,
  onChange,
}: {
  title: string;
  options: string[];
  selected: string[];
  onChange: (items: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleOutside(event: MouseEvent) {
      if (!rootRef.current) {
        return;
      }
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  function toggleItem(item: string) {
    const next = selected.includes(item)
      ? selected.filter((entry) => entry !== item)
      : [...selected, item];
    onChange(next);
    setOpen(false);
  }

  return (
    <div ref={rootRef} style={{ display: "grid", gap: 8, position: "relative" }}>
      <div style={{ fontWeight: 700, color: "#0f172a" }}>{title}</div>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        style={{
          width: "100%",
          borderRadius: 12,
          border: "1px solid #cbd5e1",
          background: "#f8fafc",
          color: "#0f172a",
          padding: "12px 14px",
          font: "inherit",
          textAlign: "left",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          cursor: "pointer",
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {selected.length > 0 ? `${selected.length} selection${selected.length > 1 ? "s" : ""}` : "Choisir une ou plusieurs options"}
        </span>
        <span style={{ color: "#64748b", fontWeight: 700 }}>{open ? "Fermer" : "Ouvrir"}</span>
      </button>

      {open ? (
        <div
          style={{
            position: "absolute",
            top: 68,
            left: 0,
            right: 0,
            zIndex: 20,
            borderRadius: 14,
            border: "1px solid #cbd5e1",
            background: "#ffffff",
            boxShadow: "0 16px 30px rgba(15, 23, 42, 0.14)",
            maxHeight: 240,
            overflowY: "auto",
            padding: 8,
            display: "grid",
            gap: 4,
          }}
        >
          {options.map((item) => {
            const active = selected.includes(item);
            return (
              <button
                key={item}
                type="button"
                onClick={() => toggleItem(item)}
                style={{
                  border: "none",
                  borderRadius: 10,
                  background: active ? "#dbeafe" : "#ffffff",
                  color: active ? "#1d4ed8" : "#0f172a",
                  padding: "10px 12px",
                  textAlign: "left",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 10,
                  cursor: "pointer",
                }}
              >
                <span>{item}</span>
                <span style={{ fontWeight: 800 }}>{active ? "Oui" : ""}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {selected.length === 0 ? (
          <span style={{ color: "#64748b", fontSize: 13 }}>Aucun element selectionne</span>
        ) : (
          selected.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onChange(selected.filter((entry) => entry !== item))}
              style={{
                borderRadius: 999,
                border: "1px solid #bfdbfe",
                background: "#eff6ff",
                color: "#1d4ed8",
                padding: "6px 10px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              {item} x
            </button>
          ))
        )}
      </div>
    </div>
  );
}
