from __future__ import annotations

import re
import unicodedata
from typing import Any


DIAGNOSIS_CATEGORY_LABELS = {
    "stable": "Etat post-operatoire stable",
    "sepsis": "Sepsis / complication infectieuse",
    "hemorragie": "Hemorragie / hypovolemie",
    "embolie_pulmonaire": "Embolie pulmonaire",
    "respiratoire": "Complication respiratoire",
    "cardiaque": "Complication cardiaque",
    "douleur": "Douleur post-operatoire",
    "autre": "Autre complication",
}

SURGERY_CATEGORY_LABELS = {
    "thoracique": "Chirurgie thoracique",
    "colorectale": "Chirurgie colorectale",
    "abdominale": "Chirurgie abdominale",
    "orthopedique": "Chirurgie orthopedique",
    "urologique": "Chirurgie urologique",
    "gynecologique": "Chirurgie gynecologique",
    "vasculaire": "Chirurgie vasculaire",
    "autre": "Autre chirurgie",
}

DIAGNOSIS_CATEGORY_KEYWORDS = {
    "stable": (
        "stable",
        "stabilise",
        "normal",
        "constantes normales",
        "constantes post-operatoires stables",
        "sans complication",
        "temoin sain",
        "evolution simple",
        "rassurant",
    ),
    "sepsis": (
        "sepsis",
        "septique",
        "infection",
        "infectieux",
        "infectieuse",
        "septicemie",
        "bacteriemie",
        "choc septique",
    ),
    "hemorragie": (
        "hemorrag",
        "saign",
        "hypovolem",
        "choc hemorr",
        "anemie aigue",
        "perte sanguine",
    ),
    "embolie_pulmonaire": (
        "embolie pulmonaire",
        "thromboembol",
        "embolie",
        "ep probable",
        "ep post-op",
    ),
    "respiratoire": (
        "respiratoire",
        "pneumopath",
        "pneumonie",
        "ira",
        "insuffisance respiratoire",
        "hypox",
        "desaturation",
        "atelect",
        "broncho",
    ),
    "cardiaque": (
        "cardiaque",
        "coronar",
        "isch",
        "arythm",
        "trouble du rythme",
        "oap",
        "bas debit",
        "insuffisance cardiaque",
        "infarct",
    ),
    "douleur": (
        "douleur",
        "algique",
        "hyperalg",
        "antalg",
        "pain",
    ),
}

SURGERY_CATEGORY_KEYWORDS = {
    "thoracique": ("thorac", "pulmona", "lobect", "pneumonect"),
    "colorectale": ("colorect", "colect", "sigmoid", "rect", "digestif bas"),
    "abdominale": ("abdominal", "digest", "hepati", "biliaire", "cholecyst", "gastrect", "append"),
    "orthopedique": ("ortho", "hanche", "genou", "rachis", "fracture", "prothese"),
    "urologique": ("urolog", "prostate", "nephr", "vessie", "ureter"),
    "gynecologique": ("gyneco", "hysterect", "ovaire", "uter", "pelvien"),
    "vasculaire": ("vascul", "anevrys", "carotide", "pontage", "aorte"),
}

DIAGNOSIS_HEURISTIC_LABELS = {
    "sepsis": "Sepsis / complication infectieuse possible",
    "hemorragie": "Hemorragie / hypovolemie possible",
    "embolie_pulmonaire": "Embolie pulmonaire possible",
    "respiratoire": "Complication respiratoire post-op (pneumopathie / IRA)",
    "cardiaque": "Complication cardiaque post-op possible",
    "douleur": "Douleur post-op non controlee possible",
}

DIAGNOSIS_FOCUS = {
    "stable": {
        "expected_signals": [
            "constantes proches du baseline",
            "absence d'alerte combinee",
            "hemodynamique preservee",
        ],
        "contradicting_signals": [
            "desaturation nouvelle",
            "hypotension",
            "fievre ou hypothermie",
            "tachypnee ou tachycardie persistante",
        ],
        "surveillance_points": [
            "surveillance standard des constantes et des symptomes",
            "verification reguliere de la tolerance clinique",
        ],
        "escalation_triggers": [
            "toute derive soutenue par rapport au baseline",
            "apparition d'alertes combinees",
        ],
    },
    "sepsis": {
        "expected_signals": [
            "fievre ou hypothermie",
            "tachycardie",
            "polypnee",
            "tendance hypotensive",
        ],
        "contradicting_signals": [
            "temperature durablement normale",
            "hemodynamique stable sans derive",
        ],
        "surveillance_points": [
            "temperature, FR, TAM, FC",
            "etat general et tolerance hemodynamique",
        ],
        "escalation_triggers": [
            "TAM < 65 mmHg",
            "aggravation respiratoire",
            "confusion ou deterioration rapide",
        ],
    },
    "hemorragie": {
        "expected_signals": [
            "tachycardie",
            "chute de TAM ou SBP",
            "shock index eleve",
        ],
        "contradicting_signals": [
            "hemodynamique durablement preservee",
            "temperature elevee au premier plan",
        ],
        "surveillance_points": [
            "FC, SBP, TAM, shock index",
            "signes de mauvaise tolerance ou de saignement",
        ],
        "escalation_triggers": [
            "hypotension persistante",
            "tachycardie croissante",
            "malaise ou signe d'hypoperfusion",
        ],
    },
    "embolie_pulmonaire": {
        "expected_signals": [
            "desaturation",
            "tachycardie",
            "polypnee",
            "bascule brutale",
        ],
        "contradicting_signals": [
            "profil lentement progressif febrile",
            "temperature elevee au premier plan",
        ],
        "surveillance_points": [
            "SpO2, FR, FC, TAM",
            "dyspnee, douleur thoracique, tolerance",
        ],
        "escalation_triggers": [
            "desaturation rapide",
            "douleur thoracique ou syncope",
            "retentissement hemodynamique",
        ],
    },
    "respiratoire": {
        "expected_signals": [
            "desaturation",
            "polypnee",
            "tendance febrile",
            "derive progressive",
        ],
        "contradicting_signals": [
            "oxygenation durablement preservee",
            "absence de derive respiratoire",
        ],
        "surveillance_points": [
            "SpO2, FR, temperature",
            "signes respiratoires fonctionnels",
        ],
        "escalation_triggers": [
            "SpO2 en baisse",
            "polypnee croissante",
            "aggravation respiratoire mal toleree",
        ],
    },
    "cardiaque": {
        "expected_signals": [
            "tachycardie",
            "hypotension",
            "desaturation moderee",
            "bascule hemodynamique",
        ],
        "contradicting_signals": [
            "profil febrile dominant",
            "hemodynamique completement stable",
        ],
        "surveillance_points": [
            "FC, TAM, SpO2",
            "douleur thoracique, dyspnee, malaise",
        ],
        "escalation_triggers": [
            "hypotension ou bas debit",
            "douleur thoracique",
            "aggravation respiratoire associee",
        ],
    },
    "douleur": {
        "expected_signals": [
            "tachycardie moderee",
            "fluctuation des constantes",
            "hemodynamique preservee",
        ],
        "contradicting_signals": [
            "hypotension",
            "desaturation significative",
            "fievre au premier plan",
        ],
        "surveillance_points": [
            "douleur, FC, FR",
            "effet des mesures antalgiques et tolerance",
        ],
        "escalation_triggers": [
            "douleur non controlee",
            "derive hemodynamique ou respiratoire associee",
        ],
    },
    "autre": {
        "expected_signals": [
            "surveillance ciblee selon le diagnostic medical valide",
        ],
        "contradicting_signals": [
            "discordance franche entre constantes et diagnostic valide",
        ],
        "surveillance_points": [
            "constantes et symptomes cibles selon le diagnostic valide",
        ],
        "escalation_triggers": [
            "aggravation clinique rapide",
            "discordance majeure avec la trajectoire attendue",
        ],
    },
}


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s/_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def infer_diagnosis_category(text: str | None) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return "autre"
    for category, keywords in DIAGNOSIS_CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "autre"


def infer_surgery_category(text: str | None) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return "autre"
    for category, keywords in SURGERY_CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "autre"


def diagnosis_category_label(category: str | None) -> str:
    return DIAGNOSIS_CATEGORY_LABELS.get(str(category or "").strip().lower(), DIAGNOSIS_CATEGORY_LABELS["autre"])


def surgery_category_label(category: str | None) -> str:
    return SURGERY_CATEGORY_LABELS.get(str(category or "").strip().lower(), SURGERY_CATEGORY_LABELS["autre"])


def diagnosis_focus(category: str | None) -> dict[str, list[str]]:
    key = str(category or "").strip().lower()
    payload = DIAGNOSIS_FOCUS.get(key) or DIAGNOSIS_FOCUS["autre"]
    return {
        "expected_signals": list(payload.get("expected_signals") or []),
        "contradicting_signals": list(payload.get("contradicting_signals") or []),
        "surveillance_points": list(payload.get("surveillance_points") or []),
        "escalation_triggers": list(payload.get("escalation_triggers") or []),
    }


def heuristic_label_for_category(category: str | None) -> str | None:
    key = str(category or "").strip().lower()
    return DIAGNOSIS_HEURISTIC_LABELS.get(key)


def build_validated_context(feedback_row: dict[str, Any] | None, *, surgery_type: str) -> dict[str, Any] | None:
    if not feedback_row:
        return None
    diagnosis = str(feedback_row.get("final_diagnosis") or "").strip()
    if not diagnosis:
        return None
    decision = str(feedback_row.get("diagnosis_decision") or "validated").strip().lower()
    if decision not in {"validated", "rejected"}:
        decision = "validated"
    diagnosis_category = str(
        feedback_row.get("final_diagnosis_class") or infer_diagnosis_category(diagnosis)
    ).strip().lower() or "autre"
    surgery_category = str(
        feedback_row.get("surgery_class") or infer_surgery_category(surgery_type)
    ).strip().lower() or "autre"
    focus = diagnosis_focus(diagnosis_category)
    return {
        "analysis_mode": "post_validation",
        "diagnosis_decision": decision,
        "validated_diagnosis": diagnosis,
        "diagnosis_category": diagnosis_category,
        "diagnosis_category_label": diagnosis_category_label(diagnosis_category),
        "surgery_category": surgery_category,
        "surgery_category_label": surgery_category_label(surgery_category),
        "surgery_type": surgery_type,
        "heuristic_label": heuristic_label_for_category(diagnosis_category),
        "focus": focus,
    }
