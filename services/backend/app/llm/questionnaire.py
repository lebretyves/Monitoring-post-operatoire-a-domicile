from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
        return {
            "responder": responder,
            "comment": comment.strip(),
            "answers": enriched_answers,
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

    alert_blob = " ".join(
        f"{alert.get('rule_id', '')} {alert.get('title', '')} {alert.get('message', '')}".lower()
        for alert in alerts
    )

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

    if hr >= 95 and rr >= 18 and spo2 >= 95 and 36.0 < temp < 38.0 and map_value >= 80:
        trigger_ids.update({"pain_like_pattern", "sympathetic_pattern"})
        summary.append("Pattern sympathique compatible avec douleur post-op sans argument infectieux ou respiratoire fort.")

    if history_points:
        start = history_points[0].get("values", {})
        spo2_delta = spo2 - float(start.get("spo2") or 0)
        if spo2_delta <= -3:
            trigger_ids.add("respiratory_trend")
            summary.append(f"Baisse de SpO2 de {int(round(abs(spo2_delta)))} points depuis J0.")

    # Remove duplicates while preserving order
    deduped_summary: list[str] = []
    for item in summary:
        if item not in deduped_summary:
            deduped_summary.append(item)

    return trigger_ids, deduped_summary
