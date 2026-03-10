from __future__ import annotations

from typing import Any


SUMMARY_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
But: orientation clinique prudente, non diagnostic, non prescription.
Regles:
- Utilise uniquement les donnees fournies.
- Distingue donnees objectives et contexte declare.
- Ne pose jamais de diagnostic certain.
- Si un danger immediat est suggere, recommande une reevaluation urgente.
- Si aucune source n'est fournie, ecris exactement: source non disponible.
- Tu ne connais pas le scenario simule interne.
- Reponse courte, concrete, sans explication de methode.
""".strip()


SCENARIO_REVIEW_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
Tu aides a confirmer ou non un scenario clinique a partir des constantes, tendances et alertes.
Regles:
- Utilise uniquement les donnees fournies.
- Reste prudent et baisse la confiance si doute.
- Distingue donnees objectives et contexte declare.
- Si danger immediat, clinical_priority = high.
- Reponds uniquement avec un objet JSON conforme.
""".strip()


CLINICAL_PACKAGE_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
Tu aides a l'orientation clinique a partir des constantes, tendances, alertes, chirurgie, jour post-op
et du contexte clinique selectionne par l'utilisateur.
Regles:
- Utilise uniquement les donnees fournies.
- Distingue donnees objectives et contexte declare.
- Les alertes simples orientent, les alertes combinees et tendances sont plus specifiques.
- Ne pose jamais de diagnostic certain.
- Si un diagnostic medical valide est fourni, ne le rediscute pas: evalue sa coherence clinique actuelle.
- Si les donnees sont rassurantes et qu'aucun signal fort n'oriente vers une complication, tu peux conclure a une stabilite clinique sans complication active evidente.
- Tu ne connais pas le scenario simule interne.
- Reponse courte, concrete, et strictement structuree.
- Reponds uniquement avec un objet JSON conforme.
""".strip()


PRIORITIZATION_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
Tu priorises les patients a revoir en premier a partir de leurs constantes, alertes, tendances et contexte clinique.
Regles:
- Utilise uniquement les donnees fournies.
- Priorise selon le risque de deterioration.
- Tu ne connais pas le scenario simule interne.
- Retourne des raisons courtes.
- Reponds uniquement avec un objet JSON conforme.
""".strip()


def _format_course_points(points: list[dict[str, Any]], *, sample_count: int = 3) -> str:
    if not points:
        return "aucune tendance disponible"
    if sample_count <= 1:
        indices = [len(points) - 1]
    else:
        step = max(1, (len(points) - 1) // (sample_count - 1))
        indices = sorted({0, *(min(len(points) - 1, step * i) for i in range(sample_count - 1)), len(points) - 1})
    lines: list[str] = []
    for index in indices:
        point = points[index]
        values = point.get("values", {})
        lines.append(
            f"- {point.get('ts')}: FC={values.get('hr')}, SpO2={values.get('spo2')}, "
            f"TAM={values.get('map')}, FR={values.get('rr')}, T={values.get('temp')}"
        )
    return "\n".join(lines)


def _format_current_vitals(last_vitals: dict[str, Any]) -> str:
    return (
        f"FC {last_vitals.get('hr')} bpm, "
        f"SpO2 {last_vitals.get('spo2')}%, "
        f"SBP {last_vitals.get('sbp')} mmHg, "
        f"DBP {last_vitals.get('dbp')} mmHg, "
        f"TAM {int(round(float(last_vitals.get('map', 0))))} mmHg, "
        f"FR {last_vitals.get('rr')}/min, "
        f"T C {last_vitals.get('temp')}"
    )


def _format_baseline_vitals(points: list[dict[str, Any]]) -> str:
    if not points:
        return "Baseline J0 non disponible."
    values = points[0].get("values", {})
    return (
        f"Baseline J0: FC {values.get('hr')} bpm, SpO2 {values.get('spo2')}%, "
        f"SBP {values.get('sbp')} mmHg, DBP {values.get('dbp')} mmHg, "
        f"TAM {values.get('map')} mmHg, FR {values.get('rr')}/min, T {values.get('temp')} C."
    )


def _course_summary(points: list[dict[str, Any]]) -> str:
    if not points:
        return "historique depuis J0 non disponible"
    start_values = points[0].get("values", {})
    end_values = points[-1].get("values", {})
    deltas = {
        "hr": _delta_text(start_values.get("hr"), end_values.get("hr"), "bpm"),
        "spo2": _delta_text(start_values.get("spo2"), end_values.get("spo2"), "%"),
        "map": _delta_text(start_values.get("map"), end_values.get("map"), "mmHg"),
        "rr": _delta_text(start_values.get("rr"), end_values.get("rr"), "/min"),
        "temp": _delta_text(start_values.get("temp"), end_values.get("temp"), "C"),
    }
    return (
        "Resume de trajectoire depuis J0: "
        f"FC {deltas['hr']}, SpO2 {deltas['spo2']}, TAM {deltas['map']}, "
        f"FR {deltas['rr']}, T {deltas['temp']}."
    )


def _find_change_onset_index(points: list[dict[str, Any]]) -> int:
    if len(points) < 2:
        return 0
    baseline = points[0].get("values", {})
    for index, point in enumerate(points[1:], start=1):
        values = point.get("values", {})
        if _has_meaningful_deviation(baseline, values):
            return index
    return max(0, len(points) - min(3, len(points)))


def _has_meaningful_deviation(baseline: dict[str, Any], values: dict[str, Any]) -> bool:
    try:
        hr_delta = abs(float(values.get("hr", 0)) - float(baseline.get("hr", 0)))
        spo2_drop = float(baseline.get("spo2", 0)) - float(values.get("spo2", 0))
        map_drop = float(baseline.get("map", 0)) - float(values.get("map", 0))
        rr_delta = abs(float(values.get("rr", 0)) - float(baseline.get("rr", 0)))
        temp_delta = abs(float(values.get("temp", 0)) - float(baseline.get("temp", 0)))
    except (TypeError, ValueError):
        return False
    return (
        hr_delta >= 10
        or spo2_drop >= 2
        or map_drop >= 5
        or rr_delta >= 4
        or temp_delta >= 0.3
    )


def _window_extrema(points: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = ("hr", "spo2", "map", "rr", "temp")
    extrema: dict[str, Any] = {}
    if not points:
        return extrema
    for metric in metrics:
        values: list[float] = []
        for point in points:
            try:
                values.append(float(point.get("values", {}).get(metric)))
            except (TypeError, ValueError):
                continue
        if not values:
            continue
        extrema[metric] = {"min": min(values), "max": max(values)}
    return extrema


def _format_change_window(points: list[dict[str, Any]]) -> str:
    if not points:
        return "Fenetre de modification non disponible."
    onset_index = _find_change_onset_index(points)
    window = points[onset_index:]
    onset_point = window[0]
    current_point = window[-1]
    onset_values = onset_point.get("values", {})
    current_values = current_point.get("values", {})
    extrema = _window_extrema(window)
    return (
        f"Fenetre de modification utile: debut apparent {onset_point.get('ts')} -> maintenant {current_point.get('ts')}.\n"
        f"- Au debut de derive: FC {onset_values.get('hr')}, SpO2 {onset_values.get('spo2')}, TAM {onset_values.get('map')}, "
        f"FR {onset_values.get('rr')}, T {onset_values.get('temp')}.\n"
        f"- Extremes observes: FC max { _pretty_number(extrema.get('hr', {}).get('max')) }, "
        f"SpO2 min { _pretty_number(extrema.get('spo2', {}).get('min')) }, "
        f"TAM min { _pretty_number(extrema.get('map', {}).get('min')) }, "
        f"FR max { _pretty_number(extrema.get('rr', {}).get('max')) }, "
        f"T max { _pretty_number(extrema.get('temp', {}).get('max')) }.\n"
        f"- Etat actuel en fin de fenetre: FC {current_values.get('hr')}, SpO2 {current_values.get('spo2')}, "
        f"TAM {current_values.get('map')}, FR {current_values.get('rr')}, T {current_values.get('temp')}."
    )


def _pretty_number(value: Any) -> str:
    if value is None:
        return "non disponible"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 0.01:
        return str(int(round(number)))
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _format_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "aucune alerte recente"
    lines: list[str] = []
    for alert in alerts[:3]:
        snapshot = alert.get("metric_snapshot") or {}
        evidence_mode = snapshot.get("evidence_mode", "non_precise")
        historical = "historique" if snapshot.get("historical_backfill") else "active"
        lines.append(
            f"- [{alert.get('level')}] {alert.get('title')} ({evidence_mode}, {historical})"
        )
    return "\n".join(lines)


def _format_clinical_context(clinical_context: dict[str, Any] | None) -> str:
    if not clinical_context:
        return "Contexte clinique selectionne: aucun element supplementaire fourni."

    patient_factors = clinical_context.get("patient_factors") or []
    perioperative_context = clinical_context.get("perioperative_context") or []
    free_text = str(clinical_context.get("free_text") or "").strip()

    lines = [
        "Contexte clinique declaratif (facteur de risque, pas preuve):",
        f"- Terrain patient: {', '.join(patient_factors) if patient_factors else 'aucun'}",
        f"- Contexte peri-op: {', '.join(perioperative_context) if perioperative_context else 'aucun'}",
    ]
    if free_text:
        lines.append(f"- Commentaire libre: {free_text}")
    questionnaire = clinical_context.get("questionnaire") or {}
    answered = questionnaire.get("answered_items") or []
    if answered:
        lines.append(f"- Reponses questionnaire: {'; '.join(answered[:6])}")
    lines.extend(_format_questionnaire_hints(questionnaire))
    return "\n".join(lines)


def _format_validated_context(validated_context: dict[str, Any] | None) -> str:
    if not validated_context:
        return ""

    focus = validated_context.get("focus") or {}
    expected = focus.get("expected_signals") or []
    contradictions = focus.get("contradicting_signals") or []
    surveillance = focus.get("surveillance_points") or []
    escalation = focus.get("escalation_triggers") or []

    lines = [
        "Validation medicale disponible:",
        f"- Mode d'analyse: {validated_context.get('analysis_mode', 'post_validation')}",
        f"- Decision medecin: {validated_context.get('diagnosis_decision', 'validated')}",
        f"- Diagnostic final valide: {validated_context.get('validated_diagnosis', 'non precise')}",
        f"- Categorie diagnostique validee: {validated_context.get('diagnosis_category_label', validated_context.get('diagnosis_category', 'autre'))}",
        f"- Categorie de chirurgie: {validated_context.get('surgery_category_label', validated_context.get('surgery_category', 'autre'))}",
    ]
    if expected:
        lines.append(f"- Signaux attendus a confronter: {', '.join(expected[:4])}")
    if contradictions:
        lines.append(f"- Signaux de discordance a signaler: {', '.join(contradictions[:4])}")
    if surveillance:
        lines.append(f"- Axes de surveillance prioritaires: {', '.join(surveillance[:4])}")
    if escalation:
        lines.append(f"- Criteres d'escalade a garder: {', '.join(escalation[:4])}")
    return "\n".join(lines)


def _format_questionnaire_hints(questionnaire: dict[str, Any]) -> list[str]:
    hints = questionnaire.get("differential_hints") or []
    if not isinstance(hints, list) or not hints:
        return []

    grouped: dict[tuple[str, bool], list[tuple[int, str]]] = {}
    for hint in hints:
        if not isinstance(hint, dict):
            continue
        label = str(hint.get("label") or "").strip()
        reason = str(hint.get("reason") or "").strip()
        if not label or not reason:
            continue
        try:
            weight = int(hint.get("weight", 1))
        except (TypeError, ValueError):
            weight = 1
        key = (label, bool(hint.get("against")))
        grouped.setdefault(key, []).append((max(1, min(weight, 4)), reason))

    if not grouped:
        return []

    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: sum(weight for weight, _reason in item[1]),
        reverse=True,
    )
    lines: list[str] = []
    for (label, against), reasons in ordered_groups[:4]:
        ordered_reasons = [reason for _weight, reason in sorted(reasons, key=lambda row: row[0], reverse=True)]
        prefix = "Questionnaire contre" if against else "Questionnaire en faveur de"
        lines.append(f"- {prefix} {label}: {'; '.join(ordered_reasons[:2])}")
    return lines


def _format_knowledge_excerpt(knowledge_excerpt: str | None) -> str:
    if not knowledge_excerpt:
        return "Source RAG: source non disponible.\n"
    return f"Extrait RAG utile:\n{knowledge_excerpt}\n"


def _delta_text(start_value: Any, end_value: Any, unit: str) -> str:
    if start_value is None or end_value is None:
        return "non disponible"
    try:
        delta = float(end_value) - float(start_value)
    except (TypeError, ValueError):
        return f"{start_value} -> {end_value} {unit}"
    if abs(delta) < 0.1:
        sign = "="
        rendered = "0"
    else:
        sign = "+" if delta > 0 else ""
        rendered = f"{delta:.1f}".rstrip("0").rstrip(".")
    return f"{start_value} -> {end_value} {unit} ({sign}{rendered})"


def _required_keys(schema: dict[str, Any]) -> str:
    required = schema.get("required", [])
    if not isinstance(required, list):
        return ""
    return ", ".join(str(item) for item in required)


def build_summary_prompt(
    patient: dict[str, Any],
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    history_points: list[dict[str, Any]],
    clinical_context: dict[str, Any] | None = None,
    knowledge_excerpt: str | None = None,
) -> str:
    return (
        "Tache unique: produire une synthese clinique courte.\n"
        "Redige uniquement en francais.\n"
        "Retourne uniquement un JSON compact de la forme {\"summary\":\"...\"}.\n"
        "Le champ summary doit tenir en 4 phrases maximum.\n"
        "Contenu attendu, dans cet ordre: etat global; signaux anormaux; hypotheses compatibles; quoi recontroler.\n"
        "Si un signe de gravite immediate est present, commence par 'Urgence potentielle a evaluer immediatement'.\n"
        "N'ajoute ni plan detaille, ni explication de methode, ni JSON imbrique.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"{_format_baseline_vitals(history_points)}\n"
        f"Dernieres constantes: {_format_current_vitals(last_vitals)}.\n"
        f"{_course_summary(history_points)}\n"
        f"{_format_change_window(history_points)}\n"
        f"{_format_clinical_context(clinical_context)}\n"
        f"Alertes recentes:\n{_format_alerts(alerts)}\n"
        f"{_format_knowledge_excerpt(knowledge_excerpt)}"
    )


def build_scenario_review_prompt(
    patient: dict[str, Any],
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    recent_points: list[dict[str, Any]],
    schema: dict[str, Any],
    clinical_context: dict[str, Any] | None = None,
    knowledge_excerpt: str | None = None,
) -> str:
    return (
        "Analyse la coherence clinique du scenario post-operatoire courant.\n"
        "Tache unique: dire si les constantes et tendances sont compatibles avec le scenario annonce.\n"
        f"Reponds en francais, uniquement dans un objet JSON avec les cles: {_required_keys(schema)}.\n"
        "Reste bref: alternatives <= 3, supporting_signals <= 4, contradicting_signals <= 3.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"Scenario courant: {last_vitals.get('scenario_label') or last_vitals.get('scenario')}\n"
        f"{_format_baseline_vitals(recent_points)}\n"
        f"Constantes actuelles: {_format_current_vitals(last_vitals)}\n"
        f"Alertes recentes:\n{_format_alerts(alerts)}\n"
        f"{_format_clinical_context(clinical_context)}\n"
        f"{_course_summary(recent_points)}\n"
        f"{_format_change_window(recent_points)}\n"
        f"{_format_knowledge_excerpt(knowledge_excerpt)}"
        "Retourne uniquement un objet JSON conforme au schema fourni."
    )


def build_clinical_package_prompt(
    patient: dict[str, Any],
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    history_points: list[dict[str, Any]],
    schema: dict[str, Any],
    clinical_context: dict[str, Any] | None = None,
    validated_context: dict[str, Any] | None = None,
    knowledge_excerpt: str | None = None,
) -> str:
    post_validation_instructions = ""
    if validated_context:
        post_validation_instructions = (
            "- Mode post-validation: hypothesis_ranking doit commencer par le diagnostic valide et qualifier sa coherence actuelle.\n"
            "- Les autres lignes servent seulement a signaler au maximum deux risques ou tensions a surveiller a court terme.\n"
            "- structured_synthesis et handoff_summary doivent partir du diagnostic valide, sans refaire un diagnostic differentiel libre.\n"
        )
    return (
        "Tache unique: produire un pack d'analyse clinique structure et compact.\n"
        f"Redige uniquement en francais dans un objet JSON avec les cles: {_required_keys(schema)}.\n"
        "Contraintes:\n"
        "- structured_synthesis: 2 phrases max.\n"
        "- alert_explanations: 3 items max, 1 phrase courte par item.\n"
        "- hypothesis_ranking: 3 hypotheses max, avec compatibility_percent entre 0 et 100 si possible.\n"
        "- arguments_for et arguments_against: 2 items max par hypothese.\n"
        "- trajectory_explanation: 1 phrase.\n"
        "- recheck_recommendations: 3 items max.\n"
        "- handoff_summary: 3 phrases max.\n"
        "- scenario_consistency: 1 phrase sur la coherence clinique observee, sans mentionner de scenario cache.\n"
        f"{post_validation_instructions}"
        "- Si les constantes et la trajectoire sont rassurantes, hypothesis_ranking peut commencer par un etat stable sans complication active evidente.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"{_format_baseline_vitals(history_points)}\n"
        f"Constantes actuelles: {_format_current_vitals(last_vitals)}\n"
        f"Alertes recentes:\n{_format_alerts(alerts)}\n"
        f"{_course_summary(history_points)}\n"
        f"{_format_change_window(history_points)}\n"
        f"{_format_validated_context(validated_context)}\n"
        f"{_format_clinical_context(clinical_context)}\n"
        f"{_format_knowledge_excerpt(knowledge_excerpt)}"
        "Retourne uniquement un objet JSON conforme au schema fourni."
    )


def build_prioritization_prompt(
    patient_snapshots: list[dict[str, Any]],
    knowledge_excerpt: str | None = None,
) -> str:
    concise_snapshots = [
        {
            "patient_id": snapshot.get("patient_id"),
            "surgery_type": snapshot.get("surgery_type"),
            "postop_day": snapshot.get("postop_day"),
            "last_vitals": snapshot.get("last_vitals"),
            "alert_levels": snapshot.get("alert_levels"),
        }
        for snapshot in patient_snapshots
    ]
    return (
        "Tache unique: prioriser les patients a revoir en premier.\n"
        "Classe les patients selon le risque actuel et evolutif de deterioration.\n"
        "Retourne uniquement un objet JSON avec la cle prioritized_patients.\n"
        "Contraintes: 1 ligne de raison courte par patient.\n"
        f"Patients a classer: {concise_snapshots}\n"
        f"{_format_knowledge_excerpt(knowledge_excerpt)}"
        "Retourne uniquement un objet JSON conforme au schema fourni."
    )
