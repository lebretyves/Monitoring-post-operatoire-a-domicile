from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


REPORT_BLUE = colors.HexColor("#103b63")
REPORT_BLUE_SOFT = colors.HexColor("#e8f1f8")
REPORT_BLUE_PANEL = colors.HexColor("#f5f9fc")
REPORT_BORDER = colors.HexColor("#c8d8e6")
REPORT_TEXT = colors.HexColor("#17324d")
REPORT_MUTED = colors.HexColor("#5f7790")
REPORT_GREEN = colors.HexColor("#dff5ea")
REPORT_AMBER = colors.HexColor("#fff1d6")
REPORT_RED = colors.HexColor("#fde4e4")

METRIC_SPECS = [
    ("hr", "FC", "bpm", 0),
    ("spo2", "SpO2", "%", 0),
    ("sbp", "PAS", "mmHg", 0),
    ("dbp", "PAD", "mmHg", 0),
    ("map", "TAM", "mmHg", 0),
    ("rr", "FR", "/min", 0),
    ("temp", "Temperature", "C", 1),
    ("shock_index", "Shock index", "", 2),
]


def render_clinical_report_pdf(report: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=28 * mm,
        bottomMargin=16 * mm,
        title=f"{report['patient_id']} report",
        author="Home Track",
        pageCompression=0,
    )
    styles = _build_styles()
    width = doc.width

    story = [
        Paragraph("Compte rendu clinique post-operatoire", styles["ReportTitle"]),
        Paragraph("Synthese de surveillance pour dossier de soins", styles["ReportSubtitle"]),
        Spacer(1, 5 * mm),
        _section_header("Identification et contexte de prise en charge", width, styles),
        _identity_table(report, width, styles),
        Spacer(1, 4 * mm),
        _status_table(report, width, styles),
        Spacer(1, 4 * mm),
        _history_alerts_table(report, width, styles),
        Spacer(1, 4 * mm),
        _section_header("Constantes de depart, valeurs actuelles et variations", width, styles),
        _vitals_table(report, width, styles),
        Spacer(1, 4 * mm),
        _section_header("Gravite clinique et synthese operative", width, styles),
        _score_summary_table(report, width, styles),
        Spacer(1, 4 * mm),
        _paragraph_block(
            "Resume clinique",
            [
                report["final_analysis"].summary_text,
                report["final_analysis"].structured_synthesis,
                report["final_analysis"].handoff_summary,
            ],
            width,
            styles,
        ),
        PageBreak(),
        _section_header("Hypotheses cliniques IA", width, styles),
        _hypothesis_table(
            report["baseline_analysis"].hypothesis_ranking,
            width,
            styles,
            title="Lecture initiale des hypotheses",
        ),
    ]

    if report["adjusted_analysis"]:
        story.extend(
            [
                Spacer(1, 4 * mm),
                _section_header("Impact du questionnaire differentiel", width, styles),
                _hypothesis_shift_table(
                    report["baseline_analysis"],
                    report["adjusted_analysis"],
                    width,
                    styles,
                ),
            ]
        )

    story.extend(
        [
            Spacer(1, 4 * mm),
            _questionnaire_block(report, width, styles),
            Spacer(1, 4 * mm),
            _analysis_notes_block(report, width, styles),
            Spacer(1, 4 * mm),
            _section_header("Conduite a tenir / surveillance", width, styles),
            _action_tables(report, width, styles),
            Spacer(1, 4 * mm),
            _section_header("Trajectoire et coherence clinique", width, styles),
            _paragraph_block(
                "Evolution observee",
                [
                    f"Trajectoire: {report['final_analysis'].trajectory_status}",
                    report["final_analysis"].trajectory_explanation,
                    report["final_analysis"].scenario_consistency,
                ],
                width,
                styles,
            ),
        ]
    )

    doc.build(
        story,
        onFirstPage=lambda canvas, pdf_doc: _draw_page_chrome(canvas, pdf_doc, report),
        onLaterPages=lambda canvas, pdf_doc: _draw_page_chrome(canvas, pdf_doc, report),
    )
    return buffer.getvalue()


def _build_styles() -> StyleSheet1:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=REPORT_TEXT,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=REPORT_MUTED,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=REPORT_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyMuted",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=REPORT_MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyStrong",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=REPORT_TEXT,
        )
    )
    return styles


def _section_header(title: str, width: float, styles: StyleSheet1) -> Table:
    table = Table([[Paragraph(_escape(title), styles["SectionLabel"])]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), REPORT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _identity_table(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    patient = report["patient"]
    last_vitals = report["last_vitals"]
    rows = [
        ["Patient ref", report["patient_id"], "Patient", patient.get("full_name", report["patient_id"])],
        ["Intervention", last_vitals.get("surgery_type", patient.get("surgery_type", "non renseignee")), "Jour post-op", _format_postop_day(last_vitals.get("postop_day", patient.get("postop_day")))],
        ["Chambre", str(last_vitals.get("room") or patient.get("room") or "N/A"), "Scenario observe", report["scenario_label"]],
        ["Derniere mesure", _format_datetime(report["last_vitals_timestamp"]), "Export", _format_datetime(report["exported_at"])],
    ]
    return _key_value_table(rows, width, styles)


def _status_table(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    final_analysis = report["final_analysis"]
    level = str(final_analysis.explanatory_score.level).upper()
    questionnaire_status = "oui" if report["adjusted_analysis"] else "non"
    rows = [
        ["Gravite clinique", level, "Source analyse", f"{final_analysis.source} / {final_analysis.llm_status}"],
        ["Score explicatif", str(final_analysis.explanatory_score.score), "Etat analyse", final_analysis.analysis_state.mode],
        ["Questionnaire applique", questionnaire_status, "Alertes recentes", str(len(report["alerts"]))],
    ]
    return _key_value_table(rows, width, styles)


def _history_alerts_table(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    patient = report["patient"]
    history_lines = patient.get("history") or []
    history_text = "<br/>".join(f"- {_escape(item)}" for item in history_lines) if history_lines else "Aucun antecedent structure disponible."
    alerts = report["alerts"]
    if alerts:
        alert_parts = []
        for alert in alerts[:5]:
            level = str(alert.get("level") or "INFO").upper()
            title = str(alert.get("title") or "Alerte")
            status = str(alert.get("status") or "OPEN")
            alert_parts.append(f"<b>[{_escape(level)}]</b> {_escape(title)} ({_escape(status)})")
        alerts_text = "<br/>".join(alert_parts)
    else:
        alerts_text = "Aucune alerte recente."

    table = Table(
        [
            [
                Paragraph("<b>Antecedents / terrain connus</b><br/>" + history_text, styles["BodySmall"]),
                Paragraph("<b>Alertes recentes</b><br/>" + alerts_text, styles["BodySmall"]),
            ]
        ],
        colWidths=[width * 0.48, width * 0.52],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), REPORT_BLUE_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _vitals_table(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    baseline = report["baseline_values"]
    current = report["last_vitals"]
    data = [[
        Paragraph("<b>Parametre</b>", styles["BodySmall"]),
        Paragraph(f"<b>Depart</b><br/>{_escape(_format_datetime(report['baseline_timestamp']))}", styles["BodySmall"]),
        Paragraph(f"<b>Actuel</b><br/>{_escape(_format_datetime(report['last_vitals_timestamp']))}", styles["BodySmall"]),
        Paragraph("<b>Variation</b>", styles["BodySmall"]),
    ]]

    for key, label, unit, decimals in METRIC_SPECS:
        baseline_value = baseline.get(key)
        current_value = current.get(key)
        data.append(
            [
                Paragraph(f"<b>{_escape(label)}</b>", styles["BodySmall"]),
                Paragraph(_escape(_format_metric(baseline_value, unit, decimals)), styles["BodySmall"]),
                Paragraph(_escape(_format_metric(current_value, unit, decimals)), styles["BodySmall"]),
                Paragraph(_escape(_format_delta(current_value, baseline_value, unit, decimals)), styles["BodySmall"]),
            ]
        )

    table = Table(data, colWidths=[width * 0.22, width * 0.25, width * 0.25, width * 0.28], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), REPORT_BLUE_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _score_summary_table(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    final_analysis = report["final_analysis"]
    score = final_analysis.explanatory_score
    reasons = score.reasons or ["Aucun motif explicatif detaille disponible."]
    left = (
        f"<b>Niveau de gravite</b><br/>{_escape(str(score.level).upper())}"
        f"<br/><br/><b>Score</b><br/>{score.score}/100"
    )
    right = "<b>Motifs principaux</b><br/>" + "<br/>".join(f"- {_escape(item)}" for item in reasons)
    table = Table([[Paragraph(left, styles["BodyStrong"]), Paragraph(right, styles["BodySmall"])]], colWidths=[width * 0.28, width * 0.72])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), _score_background(str(score.level))),
                ("BACKGROUND", (1, 0), (1, 0), REPORT_BLUE_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _hypothesis_table(rows: list[Any], width: float, styles: StyleSheet1, *, title: str) -> Table:
    data = [
        [
            Paragraph("<b>Hypothese</b>", styles["BodySmall"]),
            Paragraph("<b>%</b>", styles["BodySmall"]),
            Paragraph("<b>Arguments pour</b>", styles["BodySmall"]),
            Paragraph("<b>Arguments contre</b>", styles["BodySmall"]),
        ]
    ]
    for row in rows:
        data.append(
            [
                Paragraph(f"<b>{_escape(row.label)}</b><br/>{_escape(row.compatibility)}", styles["BodySmall"]),
                Paragraph(str(row.compatibility_percent), styles["BodyStrong"]),
                Paragraph(_bullet_html(row.arguments_for), styles["BodySmall"]),
                Paragraph(_bullet_html(row.arguments_against or ["Aucun argument fort contre documente."]), styles["BodySmall"]),
            ]
        )

    table = Table(data, colWidths=[width * 0.26, width * 0.08, width * 0.33, width * 0.33], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), REPORT_BLUE_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    wrapper = Table([[Paragraph(f"<b>{_escape(title)}</b>", styles["BodyStrong"])], [table]], colWidths=[width])
    wrapper.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), REPORT_BLUE_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return wrapper


def _hypothesis_shift_table(baseline_analysis: Any, adjusted_analysis: Any, width: float, styles: StyleSheet1) -> Table:
    labels: list[str] = []
    for row in list(baseline_analysis.hypothesis_ranking) + list(adjusted_analysis.hypothesis_ranking):
        if row.label not in labels:
            labels.append(row.label)

    data = [
        [
            Paragraph("<b>Hypothese</b>", styles["BodySmall"]),
            Paragraph("<b>Avant questionnaire</b>", styles["BodySmall"]),
            Paragraph("<b>Apres questionnaire</b>", styles["BodySmall"]),
            Paragraph("<b>Impact</b>", styles["BodySmall"]),
        ]
    ]
    for label in labels:
        before = _hypothesis_percent(baseline_analysis, label)
        after = _hypothesis_percent(adjusted_analysis, label)
        delta = after - before
        impact = f"{delta:+d} pts" if delta else "stable"
        data.append(
            [
                Paragraph(_escape(label), styles["BodySmall"]),
                Paragraph(f"{before} %", styles["BodySmall"]),
                Paragraph(f"{after} %", styles["BodySmall"]),
                Paragraph(_escape(impact), styles["BodyStrong"]),
            ]
        )

    table = Table(data, colWidths=[width * 0.46, width * 0.18, width * 0.18, width * 0.18], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), REPORT_BLUE_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _questionnaire_block(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    questionnaire_details = report["questionnaire_details"]
    questionnaire_selection = report["questionnaire_selection"]
    if questionnaire_details:
        answered_items = questionnaire_details.get("answered_items") or []
        hints = questionnaire_details.get("differential_hints") or []
        lines = [
            f"<b>Reponses</b><br/>{'<br/>'.join(f'- {_escape(item)}' for item in answered_items)}"
            if answered_items
            else "<b>Reponses</b><br/>Aucune reponse exploitable.",
        ]
        comment = str(questionnaire_details.get("comment") or "").strip()
        if comment:
            lines.append(f"<b>Commentaire clinique</b><br/>{_escape(comment)}")
        if hints:
            lines.append(
                "<b>Signaux differentiels issus du questionnaire</b><br/>"
                + "<br/>".join(
                    f"- {_escape(hint.get('label', 'Hypothese'))}: {_escape(hint.get('reason', ''))}"
                    for hint in sorted(hints, key=lambda item: int(item.get("weight", 0)), reverse=True)[:5]
                )
            )
        return _paragraph_panel("Questionnaire differentiel complete", "<br/><br/>".join(lines), width, styles)

    trigger_lines = questionnaire_selection.trigger_summary if questionnaire_selection else []
    modules = questionnaire_selection.modules if questionnaire_selection else []
    parts = []
    if trigger_lines:
        parts.append("<b>Motifs de declenchement</b><br/>" + "<br/>".join(f"- {_escape(item)}" for item in trigger_lines[:5]))
    if modules:
        module_lines = []
        for module in modules[:3]:
            questions = module.get("questions", [])[:3]
            joined = "; ".join(str(question.get("label") or "") for question in questions)
            module_lines.append(f"- {_escape(str(module.get('title') or 'Module'))}: {_escape(joined)}")
        parts.append("<b>Questions a recueillir si besoin</b><br/>" + "<br/>".join(module_lines))
    if not parts:
        parts.append("Aucun questionnaire differentiel actif au moment de l'export.")
    return _paragraph_panel("Questionnaire differentiel", "<br/><br/>".join(parts), width, styles)


def _analysis_notes_block(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    final_analysis = report["final_analysis"]
    blocks = [
        ("Explications des alertes", final_analysis.alert_explanations or ["Aucune explication detaillee disponible."]),
        ("Resume de transmission", [final_analysis.handoff_summary]),
    ]
    if report["adjusted_analysis"]:
        blocks.append(
            (
                "Lecture finale retenue",
                [
                    f"Hypothese dominante: {report['leading_hypothesis']}",
                    final_analysis.summary_text,
                ],
            )
        )

    content_rows = []
    for title, items in blocks:
        content_rows.append(
            [
                Paragraph(f"<b>{_escape(title)}</b>", styles["BodyStrong"]),
                Paragraph(_bullet_html(items), styles["BodySmall"]),
            ]
        )

    table = Table(content_rows, colWidths=[width * 0.26, width * 0.74])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), REPORT_BLUE_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _action_tables(report: dict[str, Any], width: float, styles: StyleSheet1) -> Table:
    final_analysis = report["final_analysis"]
    terrain_guidance_llm = report.get("terrain_guidance_llm") or {}
    has_reworked_guidance = bool(terrain_guidance_llm.get("available"))
    action_list = (
        terrain_guidance_llm.get("immediate_actions")
        if has_reworked_guidance
        else final_analysis.recheck_recommendations
    ) or ["Poursuivre la surveillance clinique et reevaluer si derive des constantes."]
    contingency = report["contingency_points"]
    terrain_guidance = report["terrain_guidance"]
    surveillance_points = terrain_guidance_llm.get("surveillance_points") if has_reworked_guidance else []
    escalation_points = terrain_guidance_llm.get("escalation_triggers") if has_reworked_guidance else []
    transmission_summary = terrain_guidance_llm.get("transmission_summary") if has_reworked_guidance else ""
    guidance_sources = terrain_guidance_llm.get("cited_sources") if has_reworked_guidance else []
    guidance_warning = str(terrain_guidance_llm.get("warning") or "")
    personalization_level = str(terrain_guidance_llm.get("personalization_level") or "")
    diagnosis_line = ""
    diagnosis_comment = ""
    if has_reworked_guidance:
        diagnosis_line = (
            f"Validation medecin: {terrain_guidance_llm.get('diagnosis_decision')} - "
            f"Diagnostic final: {terrain_guidance_llm.get('diagnosis_final')}"
        )
        diagnosis_comment = str(terrain_guidance_llm.get("diagnosis_comment") or "").strip()

    terrain_lines = []
    for row in terrain_guidance:
        terrain_lines.append(f"<b>{_escape(row['title'])}</b><br/>- {_escape(row['surveillance'])}<br/>- {_escape(row['prudence'])}")
    if not terrain_lines:
        terrain_lines.append("Aucun terrain particulier identifie dans les donnees structurees.")
    if has_reworked_guidance and isinstance(surveillance_points, list) and surveillance_points:
        terrain_lines.append("<b>Surveillance retravaillee (LLM)</b><br/>" + _bullet_html(surveillance_points))
    if not has_reworked_guidance:
        warning_text = guidance_warning or "Validation medecin requise avant conduite a tenir retravaillee."
        terrain_lines.append(f"<b>Conduite retravaillee</b><br/>{_escape(warning_text)}")

    rows = [
        [
            Paragraph("<b>Action list immediate</b><br/>" + _bullet_html(action_list), styles["BodySmall"]),
            Paragraph("<b>Conduite a tenir selon le terrain</b><br/>" + "<br/><br/>".join(terrain_lines), styles["BodySmall"]),
        ],
        [
            Paragraph("<b>Contingency / escalade</b><br/>" + _bullet_html(contingency), styles["BodySmall"]),
            Paragraph(
                "<b>Statut questionnaire / analyse</b><br/>"
                + _escape(
                    f"Mode {final_analysis.analysis_state.mode} - cache {final_analysis.analysis_state.cache_status} - source {final_analysis.source}/{final_analysis.llm_status}"
                ),
                styles["BodySmall"],
            ),
        ],
    ]
    if has_reworked_guidance and isinstance(escalation_points, list) and escalation_points:
        rows.append(
            [
                Paragraph("<b>Escalade retravaillee (LLM)</b><br/>" + _bullet_html(escalation_points), styles["BodySmall"]),
                Paragraph(
                    "<b>Transmission retravaillee</b><br/>"
                    + _escape(transmission_summary or "Transmission non disponible.")
                    + (f"<br/><br/><b>Personnalisation</b><br/>{_escape(personalization_level)}" if personalization_level else "")
                    + (f"<br/><br/><b>Validation</b><br/>{_escape(diagnosis_line)}" if diagnosis_line else "")
                    + (
                        f"<br/><br/><b>Commentaire medecin</b><br/>{_escape(diagnosis_comment)}"
                        if diagnosis_comment
                        else ""
                    )
                    + (
                        f"<br/><br/><b>Sources citees</b><br/>{_escape('; '.join(guidance_sources))}"
                        if isinstance(guidance_sources, list) and guidance_sources
                        else ""
                    ),
                    styles["BodySmall"],
                ),
            ]
        )
    table = Table(rows, colWidths=[width * 0.48, width * 0.52])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), REPORT_BLUE_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _paragraph_block(title: str, lines: list[str], width: float, styles: StyleSheet1) -> Table:
    cleaned = [line.strip() for line in lines if line and line.strip()]
    content = "<br/><br/>".join(_escape(line) for line in cleaned) if cleaned else "Aucun contenu disponible."
    return _paragraph_panel(title, content, width, styles)


def _paragraph_panel(title: str, content: str, width: float, styles: StyleSheet1) -> Table:
    table = Table(
        [
            [Paragraph(f"<b>{_escape(title)}</b>", styles["BodyStrong"])],
            [Paragraph(content, styles["BodySmall"])],
        ],
        colWidths=[width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), REPORT_BLUE_PANEL),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _key_value_table(rows: list[list[str]], width: float, styles: StyleSheet1) -> Table:
    data = []
    for row in rows:
        data.append(
            [
                Paragraph(f"<b>{_escape(row[0])}</b>", styles["BodyMuted"]),
                Paragraph(_escape(row[1]), styles["BodySmall"]),
                Paragraph(f"<b>{_escape(row[2])}</b>", styles["BodyMuted"]),
                Paragraph(_escape(row[3]), styles["BodySmall"]),
            ]
        )

    table = Table(data, colWidths=[width * 0.16, width * 0.34, width * 0.16, width * 0.34])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("BACKGROUND", (0, 0), (0, -1), REPORT_BLUE_PANEL),
                ("BACKGROUND", (2, 0), (2, -1), REPORT_BLUE_PANEL),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _draw_page_chrome(canvas: Any, doc: Any, report: dict[str, Any]) -> None:
    canvas.saveState()
    width, height = A4

    watermark_text, watermark_color = _medical_validation_watermark(report)
    canvas.saveState()
    canvas.setFillColor(watermark_color)
    canvas.setFont("Helvetica-Bold", 44)
    canvas.translate(width / 2, height / 2)
    canvas.rotate(33)
    canvas.drawCentredString(0, 0, watermark_text)
    canvas.restoreState()

    canvas.setFillColor(REPORT_BLUE)
    canvas.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(16 * mm, height - 7.0 * mm, "Home Track")
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(16 * mm, height - 13.0 * mm, "Dossier de soins post-operatoire")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 16 * mm, height - 7.0 * mm, f"Date/heure {_format_datetime(report['exported_at'])}")
    canvas.drawRightString(width - 16 * mm, height - 13.0 * mm, f"Patient {report['patient_id']}")

    canvas.setStrokeColor(REPORT_BORDER)
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFillColor(REPORT_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 16 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _medical_validation_watermark(report: dict[str, Any]) -> tuple[str, colors.Color]:
    guidance = report.get("terrain_guidance_llm") or {}
    decision = str(guidance.get("diagnosis_decision") or "").strip().lower()
    diagnosis_final = str(guidance.get("diagnosis_final") or "").strip()
    is_medically_validated = decision in {"validated", "rejected"} and bool(diagnosis_final)
    if is_medically_validated:
        return "VALIDATION MEDICALE", colors.HexColor("#d8f1df")
    return "EN ATTENTE DE VALIDATION MEDICALE", colors.HexColor("#f6e8c9")


def _format_metric(value: float | None, unit: str, decimals: int) -> str:
    if value is None:
        return "N/A"
    fmt = f"{{:.{decimals}f}}"
    rendered = fmt.format(float(value))
    if decimals == 0:
        rendered = rendered.split(".")[0]
    return f"{rendered} {unit}".strip()


def _format_delta(current: float | None, baseline: float | None, unit: str, decimals: int) -> str:
    if current is None or baseline is None:
        return "N/A"
    delta = float(current) - float(baseline)
    fmt = f"{{:+.{decimals}f}}"
    rendered = fmt.format(delta)
    if decimals == 0:
        rendered = rendered.split(".")[0]
    return f"{rendered} {unit}".strip()


def _format_datetime(raw_value: str) -> str:
    if not raw_value:
        return "N/A"
    try:
        normalized = raw_value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw_value


def _format_postop_day(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    try:
        return f"J+{int(value)}"
    except (TypeError, ValueError):
        return str(value)


def _score_background(level: str) -> colors.Color:
    normalized = level.lower()
    if normalized == "critical":
        return REPORT_RED
    if normalized == "high":
        return REPORT_AMBER
    if normalized == "medium":
        return REPORT_GREEN
    return REPORT_BLUE_SOFT


def _hypothesis_percent(analysis: Any, label: str) -> int:
    for row in getattr(analysis, "hypothesis_ranking", []) or []:
        if str(row.label) == label:
            return int(row.compatibility_percent)
    return 0


def _bullet_html(items: list[str]) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return "Aucun element documente."
    return "<br/>".join(f"- {_escape(item)}" for item in cleaned)


def _escape(value: Any) -> str:
    return escape(str(value or ""))
