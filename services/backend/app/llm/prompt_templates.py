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
- Tu ne connais pas le scenario simule interne.
- Reponds uniquement avec un objet JSON conforme.
""".strip()


PRIORITIZATION_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
Tu priorises les patients a revoir en premier a partir de leurs constantes, alertes, tendances et contexte clinique.
Regles:
- Utilise uniquement les donnees fournies.
- Priorise selon le risque de deterioration.
- Tu ne connais pas le scenario simule interne.
- Reponds uniquement avec un objet JSON conforme.
""".strip()


def _format_course_points(points: list[dict[str, Any]]) -> str:
    if not points:
        return "aucune tendance disponible"
    indices = sorted({0, len(points) // 3, (2 * len(points)) // 3, len(points) - 1})
    lines: list[str] = []
    for index in indices:
        point = points[index]
        values = point.get("values", {})
        lines.append(
            f"- {point.get('ts')}: FC={values.get('hr')}, SpO2={values.get('spo2')}, "
            f"SBP={values.get('sbp')}, DBP={values.get('dbp')}, TAM={values.get('map')}, "
            f"FR={values.get('rr')}, T C={values.get('temp')}"
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


def _course_summary(points: list[dict[str, Any]]) -> str:
    if not points:
        return "historique depuis J0 non disponible"
    start_values = points[0].get("values", {})
    end_values = points[-1].get("values", {})
    return (
        "Evolution depuis J0: "
        f"FC {start_values.get('hr')} -> {end_values.get('hr')} bpm, "
        f"SpO2 {start_values.get('spo2')} -> {end_values.get('spo2')}%, "
        f"SBP {start_values.get('sbp')} -> {end_values.get('sbp')} mmHg, "
        f"DBP {start_values.get('dbp')} -> {end_values.get('dbp')} mmHg, "
        f"TAM {start_values.get('map')} -> {end_values.get('map')} mmHg, "
        f"FR {start_values.get('rr')} -> {end_values.get('rr')}/min, "
        f"T C {start_values.get('temp')} -> {end_values.get('temp')}."
    )


def _format_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "aucune alerte recente"
    lines: list[str] = []
    for alert in alerts[:5]:
        snapshot = alert.get("metric_snapshot") or {}
        evidence_mode = snapshot.get("evidence_mode", "non_precise")
        historical = "historique" if snapshot.get("historical_backfill") else "active"
        lines.append(
            f"- {alert.get('created_at')}: [{alert.get('level')}] {alert.get('title')} - {alert.get('message')} "
            f"(mode {evidence_mode}, alerte {historical})"
        )
    return "\n".join(lines)


def _format_clinical_context(clinical_context: dict[str, Any] | None) -> str:
    if not clinical_context:
        return "Contexte clinique selectionne: aucun element supplementaire fourni."

    patient_factors = clinical_context.get("patient_factors") or []
    perioperative_context = clinical_context.get("perioperative_context") or []
    complications = clinical_context.get("complications_to_discuss") or []
    free_text = str(clinical_context.get("free_text") or "").strip()

    lines = [
        "Contexte clinique selectionne par l'utilisateur (declaratif, a utiliser comme facteur de risque ou piste de discussion, pas comme preuve):",
        f"- Terrain patient: {', '.join(patient_factors) if patient_factors else 'aucun'}",
        f"- Contexte peri-op: {', '.join(perioperative_context) if perioperative_context else 'aucun'}",
        f"- Complications a discuter: {', '.join(complications) if complications else 'aucune'}",
    ]
    if free_text:
        lines.append(f"- Commentaire libre: {free_text}")
    return "\n".join(lines)


def _format_knowledge_excerpt(knowledge_excerpt: str | None) -> str:
    if not knowledge_excerpt:
        return "Aucune source RAG n'est fournie dans cette requete.\n"
    return (
        "Extraits de protocole / base de connaissances fournis:\n"
        f"{knowledge_excerpt}\n"
    )


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
        "Analyse ce cas de surveillance post-operatoire a domicile.\n"
        "Redige uniquement en francais.\n"
        "Fais une aide a l'orientation clinique, pas un diagnostic.\n"
        "Retourne uniquement un JSON compact de la forme {\"summary\":\"...\"}.\n"
        "Le champ summary doit contenir les 6 rubriques demandees, en texte concis et lisible.\n"
        "Si aucun protocole ou extrait RAG n'est fourni, ecris exactement 'source non disponible' dans la section 6.\n"
        "Si un signe de gravite immediate est present, ecris dans la synthese 'Urgence potentielle a evaluer immediatement'.\n"
        "Tu ne connais pas le scenario simule interne et tu dois proposer toi-meme les hypotheses compatibles.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"Dernieres constantes: {_format_current_vitals(last_vitals)}.\n"
        f"{_course_summary(history_points)}\n"
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
        "Tu dois evaluer si les constantes, tendances et alertes sont compatibles avec le scenario annonce.\n"
        "Tu restes prudent. Tu ne fais pas de diagnostic autonome.\n"
        f"Tu reponds en francais, mais uniquement dans un objet JSON avec les cles: {_required_keys(schema)}.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"Scenario courant: {last_vitals.get('scenario_label') or last_vitals.get('scenario')}\n"
        f"Constantes actuelles: {_format_current_vitals(last_vitals)}\n"
        f"Alertes recentes:\n{_format_alerts(alerts)}\n"
        f"{_format_clinical_context(clinical_context)}\n"
        f"Evolution de J0 a maintenant:\n{_format_course_points(recent_points)}\n"
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
    knowledge_excerpt: str | None = None,
) -> str:
    return (
        "Construis un pack d'analyse clinique structure pour un patient de surveillance post-operatoire a domicile.\n"
        f"Redige uniquement en francais, mais dans un objet JSON avec les cles: {_required_keys(schema)}.\n"
        "Tu ne connais pas le scenario simule interne et tu dois proposer les complications les plus compatibles.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"Constantes actuelles: {_format_current_vitals(last_vitals)}\n"
        f"Alertes recentes:\n{_format_alerts(alerts)}\n"
        f"{_course_summary(history_points)}\n"
        f"Evolution de J0 a maintenant:\n{_format_course_points(history_points)}\n"
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
        "Priorise les patients a revoir en premier dans une file de surveillance post-operatoire a domicile.\n"
        "Classe les patients selon le risque actuel et evolutif de deterioration.\n"
        "Reste prudent et n'utilise que les donnees fournies.\n"
        "Retourne uniquement un objet JSON avec la cle prioritized_patients.\n"
        f"Patients a classer: {concise_snapshots}\n"
        f"{_format_knowledge_excerpt(knowledge_excerpt)}"
        "Retourne uniquement un objet JSON conforme au schema fourni."
    )
