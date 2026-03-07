from __future__ import annotations

from typing import Any


SUMMARY_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
Finalite: aide a l'orientation clinique et a la surveillance, non diagnostic, non prescription.
Tu ne remplaces ni un medecin, ni le SAMU, ni une decision clinique humaine.

Regles de securite:
- N'invente jamais de donnees.
- Utilise uniquement les donnees fournies.
- Si des donnees sont absentes, incoherentes, contradictoires ou trop anciennes, signale-le.
- Ne pose jamais de diagnostic certain. Utilise uniquement: possible, compatible avec, a verifier, non exclu.
- Ne donne jamais de posologie, de prescription, ni de conduite therapeutique personnalisee.
- Si aucune source clinique n'est fournie, ecris exactement: source non disponible.
- Si un signe de gravite immediate est present, priorise la securite et recommande d'appeler les urgences / le SAMU.

Signes de gravite immediate a considerer:
- SpO2 < 90%
- PAS < 90 mmHg ou TAM < 65 mmHg
- FR >= 30/min
- FC >= 130/min
- T C >= 39.0 ou < 36.0 avec alteration clinique
- douleur thoracique
- detresse respiratoire
- alteration de conscience
- aggravation brutale

Regles de confidentialite:
- N'affiche jamais de nom, prenom, adresse, telephone, date de naissance ou autre identifiant direct.
- Si un identifiant est necessaire, utilise uniquement l'identifiant pseudonymise deja fourni.

Format de sortie obligatoire:
1) Synthese
2) Signaux anormaux
3) Hypotheses prioritaires
4) Actions immediates
5) A surveiller / prochaines donnees a obtenir
6) Reference(s)
""".strip()


SCENARIO_REVIEW_SYSTEM_PROMPT = """
Tu es un assistant medical prudent de surveillance post-operatoire a domicile.
Tu aides a confirmer ou non un scenario clinique a partir des constantes, tendances et alertes.
Tu ne remplaces ni un medecin, ni le SAMU, ni une decision clinique humaine.

Regles:
- N'invente jamais de donnees.
- Ne pose jamais de diagnostic certain. Utilise uniquement une formulation prudente.
- Si un doute persiste, baisse le niveau de confiance.
- Si des donnees manquent ou sont incoherentes, mentionne-le dans note ou signaux.
- Ne mentionne jamais de donnees identifiantes directes.
- Si aucune source externe n'est fournie, considere que la source est indisponible et reste prudent.
- Si les constantes suggerent un danger immediat, clinical_priority doit etre "high" et recommended_action doit demander une reevaluation urgente / appel des urgences selon le contexte.

Tu reponds uniquement avec un objet JSON conforme au schema fourni.
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


def build_summary_prompt(
    patient: dict[str, Any],
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    history_points: list[dict[str, Any]],
) -> str:
    return (
        "Analyse ce cas de surveillance post-operatoire a domicile.\n"
        "Redige uniquement en francais.\n"
        "Fais une aide a l'orientation clinique, pas un diagnostic.\n"
        "Si aucun protocole ou extrait RAG n'est fourni, ecris exactement 'source non disponible' dans la section 6.\n"
        "Si un signe de gravite immediate est present, ecris dans la synthese 'Urgence potentielle a evaluer immediatement'.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"Scenario courant: {last_vitals.get('scenario_label') or last_vitals.get('scenario')}\n"
        f"Dernieres constantes: FC {last_vitals.get('hr')} bpm, SpO2 {last_vitals.get('spo2')}%, "
        f"SBP {last_vitals.get('sbp')} mmHg, DBP {last_vitals.get('dbp')} mmHg, "
        f"TAM {int(round(float(last_vitals.get('map', 0))))} mmHg, FR {last_vitals.get('rr')}/min, "
        f"T C {last_vitals.get('temp')}.\n"
        f"{_course_summary(history_points)}\n"
        f"Alertes recentes: {alerts[:5]}\n"
        "Aucune source RAG n'est fournie dans cette requete.\n"
    )


def build_scenario_review_prompt(
    patient: dict[str, Any],
    last_vitals: dict[str, Any],
    alerts: list[dict[str, Any]],
    recent_points: list[dict[str, Any]],
) -> str:
    return (
        "Analyse la coherence clinique du scenario post-operatoire courant.\n"
        "Tu dois evaluer si les constantes, tendances et alertes sont compatibles avec le scenario annonce.\n"
        "Tu restes prudent. Tu ne fais pas de diagnostic autonome.\n"
        "Tu reponds en francais, mais uniquement dans les champs JSON attendus.\n"
        f"Identifiant pseudonymise: {patient['id']}\n"
        f"Chirurgie: {last_vitals.get('surgery_type', patient['surgery_type'])}\n"
        f"Jour post-op: {last_vitals.get('postop_day', patient['postop_day'])}\n"
        f"Scenario courant: {last_vitals.get('scenario_label') or last_vitals.get('scenario')}\n"
        f"Constantes actuelles: {last_vitals}\n"
        f"Alertes recentes: {alerts[:5]}\n"
        f"Evolution de J0 a maintenant:\n{_format_course_points(recent_points)}\n"
        "Aucune source RAG n'est fournie dans cette requete.\n"
        "Retourne uniquement un objet JSON conforme au schema fourni."
    )
