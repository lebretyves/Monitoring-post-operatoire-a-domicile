from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


QUESTIONNAIRE_HYPOTHESIS_LABELS = {
    "respiratory": "Complication respiratoire post-op (pneumopathie / IRA)",
    "pulmonary_embolism": "Embolie pulmonaire possible",
    "sepsis": "Sepsis / complication infectieuse possible",
    "hemorrhage": "Hemorragie / hypovolemie possible",
    "pain": "Douleur post-op non controlee possible",
    "cardiac": "Complication cardiaque post-op possible",
}


@dataclass
class QuestionnaireSelection:
    modules: list[dict[str, Any]]
    trigger_summary: list[str]


class QuestionnaireEngine:
    def __init__(self, config_path: Path) -> None:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        self.modules = payload.get("modules", [])

    def select_modules(
        self,
        *,
        last_vitals: dict[str, Any],
        alerts: list[dict[str, Any]],
        history_points: list[dict[str, Any]],
    ) -> QuestionnaireSelection:
        trigger_ids, trigger_summary = _derive_triggers(last_vitals, alerts, history_points)
        modules: list[dict[str, Any]] = []
        for module in self.modules:
            matching = [trigger for trigger in module.get("trigger_ids", []) if trigger in trigger_ids]
            if not matching:
                continue
            row = dict(module)
            row["matched_triggers"] = matching
            modules.append(row)

        modules.sort(key=lambda row: len(row.get("matched_triggers", [])), reverse=True)
        return QuestionnaireSelection(modules=modules[:3], trigger_summary=trigger_summary)

    def enrich_answers(
        self,
        answers: list[dict[str, str]],
        *,
        responder: str,
        comment: str,
    ) -> dict[str, Any]:
        index = self._index()
        enriched_answers: list[dict[str, Any]] = []
        for answer in answers:
            module = index["modules"].get(answer["module_id"])
            question = index["questions"].get((answer["module_id"], answer["question_id"]))
            if not module or not question:
                continue
            answer_value = str(answer.get("answer", "")).strip()
            option_label = next(
                (
                    str(option.get("label"))
                    for option in question.get("options", [])
                    if str(option.get("value")) == answer_value
                ),
                answer_value,
            )
            enriched_answers.append(
                {
                    "module_id": answer["module_id"],
                    "module_title": module.get("title", answer["module_id"]),
                    "question_id": answer["question_id"],
                    "question_label": question.get("label", answer["question_id"]),
                    "answer": answer_value,
                    "answer_label": option_label,
                }
            )
        answered_items = [
            f"[{answer.get('module_title')}] {answer.get('question_label')}: {answer.get('answer_label')}"
            for answer in enriched_answers
        ]
        return {
            "responder": responder,
            "comment": comment.strip(),
            "answers": enriched_answers,
            "answered_items": answered_items,
            "differential_hints": _derive_differential_hints(enriched_answers),
        }

    def format_responses(self, payload: dict[str, Any] | None) -> str:
        if not payload:
            return "Questionnaire differentiel: aucune reponse complementaire disponible."

        responder = str(payload.get("responder") or "non precise")
        comment = str(payload.get("comment") or "").strip()
        answers = payload.get("answers") or []
        if not isinstance(answers, list) or not answers:
            return "Questionnaire differentiel: aucune reponse complementaire disponible."

        lines = [f"Questionnaire differentiel complete par: {responder}"]
        for answer in answers:
            lines.append(
                f"- [{answer.get('module_title')}] {answer.get('question_label')}: {answer.get('answer_label')}"
            )
        if comment:
            lines.append(f"- Commentaire questionnaire: {comment}")
        return "\n".join(lines)

    def _index(self) -> dict[str, Any]:
        modules = {str(module.get("id")): module for module in self.modules}
        questions: dict[tuple[str, str], dict[str, Any]] = {}
        for module in self.modules:
            module_id = str(module.get("id"))
            for question in module.get("questions", []):
                questions[(module_id, str(question.get("id")))] = question
        return {"modules": modules, "questions": questions}


def _derive_triggers(
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    history_points: list[dict[str, Any]],
) -> tuple[set[str], list[str]]:
    trigger_ids: set[str] = set()
    summary: list[str] = []

    hr = float(last_vitals.get("hr") or 0)
    spo2 = float(last_vitals.get("spo2") or 0)
    rr = float(last_vitals.get("rr") or 0)
    temp = float(last_vitals.get("temp") or 0)
    map_value = float(last_vitals.get("map") or 0)
    shock_index = float(last_vitals.get("shock_index") or 0)
    hr_delta = 0.0
    spo2_delta = 0.0
    rr_delta = 0.0
    temp_delta = 0.0
    map_delta = 0.0
    shock_index_delta = 0.0

    alert_blob = " ".join(
        f"{alert.get('rule_id', '')} {alert.get('title', '')} {alert.get('message', '')}".lower()
        for alert in alerts
    )

    if history_points:
        start = history_points[0].get("values", {})
        hr_delta = hr - float(start.get("hr") or 0)
        spo2_delta = spo2 - float(start.get("spo2") or 0)
        rr_delta = rr - float(start.get("rr") or 0)
        temp_delta = temp - float(start.get("temp") or 0)
        map_delta = map_value - float(start.get("map") or 0)
        shock_index_delta = shock_index - float(start.get("shock_index") or 0)

    if "resp" in alert_blob or "desat" in alert_blob or spo2 < 94 or rr >= 22:
        trigger_ids.update({"respiratory_alert"})
        summary.append("Suspicion respiratoire initiale sur desaturation / tachypnee / alertes respiratoires.")
    if spo2 < 94:
        trigger_ids.add("desaturation")
        summary.append(f"SpO2 basse a {int(round(spo2))}%.")
    if rr >= 22:
        trigger_ids.add("tachypnea")
        summary.append(f"FR elevee a {int(round(rr))}/min.")

    if "sepsis" in alert_blob or "infect" in alert_blob or temp >= 38.0 or temp <= 36.0:
        trigger_ids.add("infectious_alert")
        summary.append("Suspicion infectieuse initiale sur temperature / alertes compatibles.")
    if temp >= 38.0 or temp <= 36.0:
        trigger_ids.add("fever_abnormal")
        summary.append(f"Temperature anormale a {temp:.1f} C.")
    if hr >= 110 and rr >= 22 and (temp >= 38.0 or temp <= 36.0):
        trigger_ids.add("inflammatory_cluster")
        summary.append("Cluster inflammatoire possible: FC, FR et temperature anormales.")
    if (
        "infectious_alert" not in trigger_ids
        and (
            temp_delta >= 0.4
            or (temp >= 37.7 and (hr >= 95 or rr >= 20))
            or (hr_delta >= 12 and rr_delta >= 4)
            or (map_delta <= -5 and (temp_delta >= 0.3 or temp >= 37.6))
        )
    ):
        trigger_ids.add("infectious_alert")
        summary.append("Signal infectieux discret mais coherent: derive thermique ou cluster FC/FR progressif.")
    if (
        "fever_abnormal" not in trigger_ids
        and temp >= 37.7
        and (temp_delta >= 0.4 or hr_delta >= 10 or rr_delta >= 4)
    ):
        trigger_ids.add("fever_abnormal")
        summary.append(f"Temperature en derive a {temp:.1f} C avec tendance compatible.")

    if "shock" in alert_blob or "hemo" in alert_blob or "map" in alert_blob or map_value < 70 or shock_index >= 0.9:
        trigger_ids.add("hemodynamic_alert")
        summary.append("Suspicion hemodynamique initiale sur hypotension / shock index / alertes de choc.")
    if map_value < 70:
        trigger_ids.add("low_map")
        summary.append(f"TAM basse a {int(round(map_value))} mmHg.")
    if shock_index >= 0.9:
        trigger_ids.add("high_shock_index")
        summary.append(f"Shock index eleve a {shock_index:.2f}.")
    if map_value < 70 or (shock_index >= 0.9 and hr >= 110):
        trigger_ids.add("circulatory_instability")
    if (
        "hemodynamic_alert" not in trigger_ids
        and (
            (hr_delta >= 10 and (map_delta <= -5 or shock_index_delta >= 0.12))
            or (shock_index >= 0.82 and map_delta <= -4)
            or (hr >= 95 and map_value <= 82 and spo2 >= 94 and temp < 38.0)
        )
    ):
        trigger_ids.add("hemodynamic_alert")
        summary.append("Suspicion hemodynamique discrete: derive FC/TAM ou shock index en hausse depuis J0.")
    if (
        "circulatory_instability" not in trigger_ids
        and hr_delta >= 12
        and map_delta <= -6
        and spo2 >= 94
        and temp < 38.0
    ):
        trigger_ids.add("circulatory_instability")
        summary.append("Instabilite circulatoire progressive possible malgre une presentation encore compensee.")

    if (
        95 <= hr < 115
        and 18 <= rr <= 22
        and spo2 >= 96
        and 36.0 < temp < 37.8
        and map_value >= 85
        and abs(temp_delta) < 0.4
        and spo2_delta > -2
        and map_delta > -5
        and shock_index < 0.85
    ):
        trigger_ids.update({"pain_like_pattern", "sympathetic_pattern"})
        summary.append("Pattern sympathique compatible avec douleur post-op sans argument infectieux ou respiratoire fort.")

    if history_points:
        if spo2_delta <= -3:
            trigger_ids.add("respiratory_trend")
            summary.append(f"Baisse de SpO2 de {int(round(abs(spo2_delta)))} points depuis J0.")
        elif spo2_delta <= -2 and rr_delta >= 4:
            trigger_ids.add("respiratory_trend")
            summary.append("Derive respiratoire discrete depuis J0 avec baisse de SpO2 et hausse de FR.")

    # Remove duplicates while preserving order
    deduped_summary: list[str] = []
    for item in summary:
        if item not in deduped_summary:
            deduped_summary.append(item)

    return trigger_ids, deduped_summary


def _derive_differential_hints(answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (str(answer.get("module_id") or ""), str(answer.get("question_id") or "")): str(answer.get("answer") or "")
        .strip()
        .lower()
        for answer in answers
    }
    hints: list[dict[str, Any]] = []

    def get_answer(module_id: str, question_id: str) -> str:
        return lookup.get((module_id, question_id), "")

    def add(target: str, weight: int, reason: str, *, against: bool = False) -> None:
        label = QUESTIONNAIRE_HYPOTHESIS_LABELS[target]
        hints.append(
            {
                "label": label,
                "weight": max(1, min(int(weight), 4)),
                "reason": reason,
                "against": against,
            }
        )

    dyspnea_onset = get_answer("respiratory_differential", "dyspnea_onset")
    if dyspnea_onset == "brutal":
        add("pulmonary_embolism", 3, "Dyspnee d'installation brutale rapportee.")
        add("respiratory", 2, "Installation non progressive rapportee, moins specifique d'une pneumopathie.", against=True)
    elif dyspnea_onset == "progressif":
        add("respiratory", 3, "Dyspnee progressive rapportee.")
        add("pulmonary_embolism", 2, "Evolution progressive rapportee, moins specifique d'une embolie pulmonaire.", against=True)

    chest_pain_type = get_answer("respiratory_differential", "chest_pain_type")
    if chest_pain_type == "pleurale":
        add("pulmonary_embolism", 3, "Douleur thoracique pleurale rapportee.")
    elif chest_pain_type == "toux":
        add("respiratory", 2, "Douleur thoracique surtout a la toux, compatible avec une atteinte respiratoire infectieuse.")
    elif chest_pain_type == "oppressive":
        add("cardiac", 3, "Douleur thoracique oppressante rapportee.")
        add("pulmonary_embolism", 1, "Douleur non pleurale, moins typique d'une embolie pulmonaire.", against=True)

    cough = get_answer("respiratory_differential", "cough")
    if cough == "yes":
        add("respiratory", 2, "Toux rapportee.")
    elif cough == "no":
        add("respiratory", 2, "Absence de toux rapportee, moins compatible avec une pneumopathie.", against=True)

    sputum = get_answer("respiratory_differential", "sputum")
    if sputum == "purulent":
        add("respiratory", 3, "Expectoration purulente rapportee.")
        add("pulmonary_embolism", 1, "Crachats purulents peu compatibles avec une embolie pulmonaire isolee.", against=True)
    elif sputum == "clear":
        add("respiratory", 1, "Expectoration rapportee.")
    elif sputum == "none":
        add("respiratory", 2, "Absence d'expectorations rapportee, ce qui affaiblit l'hypothese respiratoire infectieuse.", against=True)

    hemoptysis = get_answer("respiratory_differential", "hemoptysis")
    if hemoptysis == "yes":
        add("pulmonary_embolism", 3, "Hemoptysie rapportee.")

    calf_pain_swelling = get_answer("respiratory_differential", "calf_pain_swelling")
    if calf_pain_swelling == "yes":
        add("pulmonary_embolism", 4, "Douleur ou gonflement de mollet rapporte.")

    chills = get_answer("infectious_differential", "chills")
    if chills == "yes":
        add("sepsis", 2, "Fievre ressentie ou frissons rapportes.")
        add("respiratory", 1, "Frissons associes a une atteinte respiratoire possible.")
    elif chills == "no":
        add("sepsis", 1, "Absence de frissons rapportee.", against=True)

    wound_redness = get_answer("infectious_differential", "wound_redness")
    if wound_redness == "yes":
        add("sepsis", 3, "Rougeur ou inflammation de plaie rapportee.")

    wound_discharge = get_answer("infectious_differential", "wound_discharge")
    if wound_discharge == "yes":
        add("sepsis", 3, "Ecoulement ou suppuration de plaie rapporte.")

    urinary_burning = get_answer("infectious_differential", "urinary_burning")
    if urinary_burning == "yes":
        add("sepsis", 2, "Brulures urinaires rapportees.")

    unusual_abdominal_pain = get_answer("infectious_differential", "unusual_abdominal_pain")
    if unusual_abdominal_pain == "yes":
        add("sepsis", 2, "Douleurs abdominales inhabituelles rapportees.")
        add("hemorrhage", 1, "Douleurs abdominales inhabituelles a confronter a une cause hemorragique.")

    visible_bleeding = get_answer("hemodynamic_differential", "visible_bleeding")
    if visible_bleeding == "yes":
        add("hemorrhage", 4, "Saignement visible rapporte.")

    dressing_saturated = get_answer("hemodynamic_differential", "dressing_saturated")
    if dressing_saturated == "yes":
        add("hemorrhage", 3, "Pansement sature ou anormalement souille rapporte.")

    syncope_malaise = get_answer("hemodynamic_differential", "syncope_malaise")
    if syncope_malaise == "yes":
        add("hemorrhage", 2, "Malaise ou syncope rapporte.")
        add("cardiac", 2, "Malaise ou syncope compatible avec une complication cardiaque.")

    oppressive_chest_pain = get_answer("hemodynamic_differential", "oppressive_chest_pain")
    if oppressive_chest_pain == "yes":
        add("cardiac", 4, "Douleur thoracique oppressante rapportee.")

    palpitations = get_answer("hemodynamic_differential", "palpitations")
    if palpitations == "yes":
        add("cardiac", 3, "Palpitations ou rythme irregulier rapportes.")

    pain_at_rest = get_answer("pain_differential", "pain_at_rest")
    if pain_at_rest == "severe":
        add("pain", 2, "Douleur importante meme au repos.")
    elif pain_at_rest == "moderate":
        add("pain", 1, "Douleur moderee au repos.")

    pain_with_mobilization = get_answer("pain_differential", "pain_with_mobilization")
    if pain_with_mobilization == "yes":
        add("pain", 3, "Douleur majoree a la mobilisation.")

    pain_with_cough = get_answer("pain_differential", "pain_with_cough")
    if pain_with_cough == "yes":
        add("pain", 2, "Douleur majoree a la toux, compatible avec une douleur mecano-post-operatoire.")

    pain_with_deep_breath = get_answer("pain_differential", "pain_with_deep_breath")
    if pain_with_deep_breath == "yes":
        add("pain", 1, "Douleur augmentee a l'inspiration profonde.")

    improved_after_rest_or_analgesia = get_answer("pain_differential", "improved_after_rest_or_analgesia")
    if improved_after_rest_or_analgesia == "yes":
        add("pain", 3, "Amelioration apres repos ou antalgie rapportee.")
        add("sepsis", 1, "Amelioration apres repos ou antalgie, moins specifique d'une complication infectieuse.", against=True)
        add("hemorrhage", 1, "Amelioration apres repos ou antalgie, moins specifique d'une complication hemorragique.", against=True)
        add("cardiac", 1, "Amelioration apres repos ou antalgie, moins specifique d'une complication cardiaque.", against=True)
    elif improved_after_rest_or_analgesia == "no":
        add("pain", 2, "Absence d'amelioration apres repos ou antalgie, ce qui affaiblit l'hypothese douloureuse isolee.", against=True)

    deduped_hints: list[dict[str, Any]] = []
    seen: set[tuple[str, bool, str]] = set()
    for hint in hints:
        key = (str(hint["label"]), bool(hint["against"]), str(hint["reason"]))
        if key in seen:
            continue
        seen.add(key)
        deduped_hints.append(hint)
    return deduped_hints
