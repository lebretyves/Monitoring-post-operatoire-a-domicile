from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_OUTPUT_ROOT = Path("/app/runtime") if Path("/app/runtime").exists() else ROOT / "runtime"
OUTPUT_PDF = RUNTIME_OUTPUT_ROOT / "home-track-architecture-audit.pdf"
OUTPUT_MD = RUNTIME_OUTPUT_ROOT / "home-track-architecture-audit.md"
SPEC_PDF = ROOT / "runtime" / "project-spec.pdf"

REPORT_BLUE = colors.HexColor("#103b63")
REPORT_BLUE_SOFT = colors.HexColor("#e8f1f8")
REPORT_BLUE_PANEL = colors.HexColor("#f5f9fc")
REPORT_BORDER = colors.HexColor("#c8d8e6")
REPORT_TEXT = colors.HexColor("#17324d")
REPORT_MUTED = colors.HexColor("#5f7790")
REPORT_GREEN = colors.HexColor("#dff5ea")
REPORT_AMBER = colors.HexColor("#fff1d6")
REPORT_RED = colors.HexColor("#fde4e4")


@dataclass
class AuditContext:
    generated_at: str
    cases_catalog: dict[str, Any]
    simulation_config: dict[str, Any]
    alert_rules: dict[str, Any]
    questionnaire_rules: dict[str, Any]
    frontend_package: dict[str, Any]
    backend_requirements: list[str]
    patient_factors: list[str]
    periop_context: list[str]
    test_count: int
    rule_levels: Counter[str]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract_string_array(path: Path, const_name: str) -> list[str]:
    content = path.read_text(encoding="utf-8")
    match = re.search(rf"const {re.escape(const_name)} = \[(.*?)\];", content, re.S)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def count_tests(path: Path) -> int:
    total = 0
    for file_path in path.rglob("test_*.py"):
        total += len(re.findall(r"^def test_", file_path.read_text(encoding="utf-8"), re.M))
    return total


def build_context() -> AuditContext:
    alert_rules = load_json(ROOT / "config" / "alert_rules.json")
    return AuditContext(
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        cases_catalog=load_json(ROOT / "config" / "cases_catalog.json"),
        simulation_config=load_json(ROOT / "config" / "simulation_scenarios.json"),
        alert_rules=alert_rules,
        questionnaire_rules=load_json(ROOT / "config" / "questionnaire_rules.json"),
        frontend_package=load_json(ROOT / "services" / "frontend" / "package.json"),
        backend_requirements=load_lines(ROOT / "services" / "backend" / "requirements.txt"),
        patient_factors=extract_string_array(
            ROOT / "services" / "frontend" / "src" / "components" / "ClinicalContextPanel.tsx",
            "PATIENT_FACTORS",
        ),
        periop_context=extract_string_array(
            ROOT / "services" / "frontend" / "src" / "components" / "ClinicalContextPanel.tsx",
            "PERIOPERATIVE_CONTEXT",
        ),
        test_count=count_tests(ROOT / "services" / "backend" / "app" / "tests"),
        rule_levels=Counter(str(rule.get("level") or "UNKNOWN") for rule in alert_rules.get("rules", [])),
    )


def build_styles() -> StyleSheet1:
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
            fontSize=8.8,
            leading=11.5,
            textColor=REPORT_TEXT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyStrong",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.6,
            leading=12.4,
            textColor=REPORT_TEXT,
        )
    )
    return styles


def _escape(text: Any) -> str:
    return escape(str(text))


def _html_join(lines: Iterable[str]) -> str:
    return "<br/>".join(_escape(line) for line in lines if str(line).strip())


def _bullet_html(items: Iterable[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return "Aucun element."
    return "<br/>".join(f"- {_escape(item)}" for item in cleaned)


def section_header(title: str, width: float, styles: StyleSheet1) -> Table:
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


def paragraph_block(title: str, body_lines: list[str], width: float, styles: StyleSheet1) -> Table:
    table = Table(
        [
            [Paragraph(f"<b>{_escape(title)}</b>", styles["BodyStrong"])],
            [Paragraph(_html_join(body_lines), styles["BodySmall"])],
        ],
        colWidths=[width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), REPORT_BLUE_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def bullet_panel(title: str, items: list[str], width: float, styles: StyleSheet1, *, tone: str = "neutral") -> Table:
    background = REPORT_BLUE_PANEL
    if tone == "good":
        background = REPORT_GREEN
    elif tone == "warn":
        background = REPORT_AMBER
    elif tone == "risk":
        background = REPORT_RED

    table = Table(
        [
            [Paragraph(f"<b>{_escape(title)}</b>", styles["BodyStrong"])],
            [Paragraph(_bullet_html(items), styles["BodySmall"])],
        ],
        colWidths=[width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def generic_table(headers: list[str], rows: list[list[Any]], col_widths: list[float], styles: StyleSheet1) -> Table:
    data = [[Paragraph(f"<b>{_escape(cell)}</b>", styles["BodySmall"]) for cell in headers]]
    for row in rows:
        data.append([Paragraph(_escape(cell), styles["BodySmall"]) for cell in row])
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), REPORT_BLUE_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, REPORT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def spec_rows(ctx: AuditContext) -> list[list[str]]:
    active_slots = len(ctx.simulation_config.get("patient_plan", []))
    case_count = len(ctx.cases_catalog.get("cases", []))
    return [
        [
            "M1 Simulateur multi-patients",
            "OK+",
            f"{active_slots} slots actifs, {case_count} cas catalogue, FC/SpO2/SBP/DBP/MAP/RR/T. La severite est portee par le scenario plus que par un simple champ profile.",
            "config/simulation_scenarios.json, config/cases_catalog.json, services/simulator/app",
        ],
        [
            "M2 Communication MQTT",
            "OK",
            "Topics structures patients/{id}/vitals, topic de controle simulator/control/refresh, QoS 1.",
            "docker-compose.yml, infra/mosquitto/mosquitto.conf, services/backend/app/mqtt",
        ],
        [
            "M3 Stockage temps reel",
            "OK+",
            "InfluxDB pour les series temporelles et PostgreSQL pour le relationnel.",
            "services/backend/app/storage, infra/postgres/init.sql",
        ],
        [
            "M4 Dashboard web",
            "OK",
            "Dashboard React temps reel, page liste + detail, graphiques, alertes et exports.",
            "services/frontend/src",
        ],
        [
            "M5 Systeme d alertes",
            "OK+",
            "Trois niveaux INFO/WARNING/CRITICAL, alertes simples, composites, tendances et incertitude.",
            "config/alert_rules.json, services/backend/app/alerting",
        ],
        [
            "M6 Docker Compose",
            "OK",
            "La stack complete demarre avec docker compose up. start-demo.ps1 ajoute une ergonomie Windows utile.",
            "docker-compose.yml, start-demo.ps1",
        ],
        [
            "M7 Documentation",
            "OK",
            "README, Mermaid, API, data model, cas cliniques, questionnaire et references.",
            "README.md, docs/*.md",
        ],
    ]


def bonus_rows() -> list[list[str]]:
    return [
        ["Detection d anomalies", "Partiel", "IsolationForest cote backend, non remonte en UI."],
        ["LLM / resumes", "OK+", "Ollama + Qwen, clinical package JSON, fallback local."],
        ["Alertes composites", "OK", "Composite baisse SpO2 + hausse FC, hemorragie J+2, detresse respiratoire."],
        ["Historique et tendances", "OK+", "Depuis J0, 24h, 6h, 1h."],
        ["Base profils patients", "Partiel", "Patients/antecedents/chirurgie ok, age-baseline-notes non persistes."],
        ["Notifications et exports", "OK+", "Centre de notifications + navigateur + CSV/PDF."],
        ["Scenarios scripts", "OK+", "Catalogue de cas, ponderation chirurgie/jour post-op, timelines realistes."],
    ]


def service_rows() -> list[list[str]]:
    return [
        ["mosquitto", "Broker MQTT", "eclipse-mosquitto:2", "1883", "Broker demo, allow_anonymous=true, persistence=false"],
        ["influxdb", "Series temporelles", "influxdb:2.7", "8086", "Measurement vitals, bucket unique, volume persistant"],
        ["postgres", "Relationnel", "postgres:16", "5432", "Patients, alerts, notes, cache LLM, feedback, notifications"],
        ["backend", "API + ingestion", "build services/backend", "8000", "FastAPI, consumer MQTT, alerting, ML, LLM, PDF"],
        ["simulator", "Generateur clinique", "build services/simulator", "-", "Publie l historique J0->maintenant puis le live toutes les 5 secondes"],
        ["frontend", "Dashboard React", "build services/frontend", "5173", "Routes / et /patients/:id, REST + WebSocket"],
        ["ollama", "LLM local", "ollama/ollama:latest", "11434", "Optionnel par flag ENABLE_LLM, fallback local si indisponible"],
    ]


def simulator_weight_rows(ctx: AuditContext) -> list[list[str]]:
    weighting = ctx.cases_catalog.get("surgery_weighting", {})
    return [
        ["Bande forte", str(weighting.get("strong", 70)), "Chirurgies les plus coherentes avec la complication"],
        ["Bande moyenne", str(weighting.get("medium", 20)), "Chirurgies plausibles mais moins typiques"],
        ["Bande faible", str(weighting.get("weak", 10)), "Variantes demo marginales"],
    ]


def scenario_case_bullets(ctx: AuditContext) -> list[str]:
    bullets: list[str] = []
    for case in ctx.cases_catalog.get("cases", []):
        weights = case.get("postop_day_weights", {})
        postop_label = ", ".join(f"J{day}:{weight}" for day, weight in weights.items()) or f"J{case.get('postop_day')}"
        surgery_pool = case.get("surgery_pool", {})
        pool_label = ""
        if surgery_pool:
            pool_label = (
                f" | pool forte={len(surgery_pool.get('strong', []))}, "
                f"moyenne={len(surgery_pool.get('medium', []))}, faible={len(surgery_pool.get('weak', []))}"
            )
        bullets.append(
            f"{case['case_id']} -> {case['scenario']} | chirurgie par defaut: {case['surgery_type']} | "
            f"jour pondere: {postop_label}{pool_label} | terrain: {', '.join(case.get('history', [])) or 'aucun'}"
        )
    return bullets


def scenario_engine_bullets(ctx: AuditContext) -> list[str]:
    catalog = ctx.simulation_config.get("scenario_catalog", {})
    bullets: list[str] = []
    for name, config in catalog.items():
        bullets.append(
            f"{name}: {config.get('label', name)} | phases={len(config.get('timeline', []))} | "
            f"delay={'oui' if 'onset_delay_range_minutes' in config else 'non'} | "
            f"repeat={'oui' if bool(config.get('repeat_timeline')) else 'non'} | "
            f"initial_shift_by_postop_day={'oui' if 'initial_shift_by_postop_day' in config else 'non'}"
        )
    return bullets


def alert_threshold_rows(ctx: AuditContext) -> list[list[str]]:
    thresholds = ctx.alert_rules.get("thresholds", {})
    rows: list[list[str]] = []
    for metric in ("spo2", "hr", "sbp", "map", "rr", "temp", "shock_index"):
        values = thresholds.get(metric, {})
        rows.append(
            [metric, str(values.get("info", "-")), str(values.get("warning", "-")), str(values.get("critical", values.get("low_critical", "-")))]
        )
    return rows


def immediate_criticality_rows() -> list[list[str]]:
    return [
        ["SpO2 < seuil critique", "+35", "Oxygene tres bas"],
        ["MAP < seuil critique", "+35", "Hypoperfusion immediate"],
        ["Shock index >= seuil critique", "+20", "Instabilite circulatoire"],
        ["FC >= seuil critique", "+18", "Tachycardie critique"],
        ["FR >= seuil critique", "+18", "Detresse respiratoire possible"],
        ["Temperature hors zone critique", "+14", "Hyperthermie ou hypothermie marquante"],
    ]


def explanatory_score_rows() -> list[list[str]]:
    return [
        ["Alerte critique active", "+35", "Poids le plus fort du score explicatif"],
        ["Alerte warning active", "+18", "Signal clinique modere"],
        ["SpO2 < 92 / < 95", "+18 / +10", "Gradient de desaturation"],
        ["FR >= 24 / >= 22", "+12 / +8", "Gradient de polypnee"],
        ["TAM < 70 / < 80", "+18 / +8", "Gradient hemodynamique"],
        ["Shock index >= 1.0 / >= 0.9", "+15 / +10", "Heuristique de choc"],
        ["FC >= 120 / >= 105", "+10 / +6", "Tachycardie brute"],
        ["Derives depuis J0", "+7 a +10", "Spo2, TAM, FC, FR, temperature"],
        ["Questionnaire", "jusqu a +6 par hint", "Poids = min(6, weight*2), uniquement pour les indices positifs"],
    ]


def questionnaire_weight_rows() -> list[list[str]]:
    return [
        ["Selection des modules", "triggers derives des vitaux + alertes + deltas historiques", "services/backend/app/llm/questionnaire.py"],
        ["Poids des hints", "1 a 4", "Chaque reponse peut ajouter ou soustraire de la credibilite par hypothese"],
        ["Poids utilise dans le score explicatif", "weight*2 plafonne a 6", "Seuls les hints en faveur sont repris"],
        ["Modules actifs", "4", "Respiratoire, infectieux, hemodynamique, douleur"],
    ]


def evolving_risk_rows() -> list[list[str]]:
    return [
        ["pneumonia_ira", "Desaturation, FR, temperature, persistence 6h", "aucune penalite forte", "100"],
        ["sepsis_progressive", "Temperature, FC, FR, baisse DBP/MAP, shock index", "aucune penalite forte", "100"],
        ["hemorrhage_low_grade", "FC/TAM/shock index progressifs, afebrile", "temperature elevee -12", "100"],
        ["hemorrhage_j2", "Bascule 1h FC + TAM + SBP + shock index", "temperature elevee -10", "100"],
        ["pulmonary_embolism", "Desaturation brutale, FC/FR 1h", "temperature elevee -4", "100"],
        ["pain_postop_uncontrolled", "FC/TA/FR moderes avec oxygene preserve", "temperature, desaturation ou instabilite -12", "65"],
        ["cardiac_postop_slow", "MAP, shock index, FC, pattern bas debit", "fievre ou pattern trop respiratoire", "100"],
        ["cardiac_postop_complication", "Bascule 1h MAP + shock index + FC", "fievre ou tableau trop respiratoire", "100"],
    ]


def clinical_source_rows() -> list[list[str]]:
    return [
        ["ARISCAT", "docs/terrain-risk-weighting.md", "Risque pulmonaire et poids respiratoires"],
        ["Caprini", "docs/terrain-risk-weighting.md", "Risque thromboembolique"],
        ["RCRI", "docs/terrain-risk-weighting.md", "Risque cardiaque peri-operatoire"],
        ["NEWS2 / NICE sepsis / AHRQ", "docs/clinical-references.md", "Seuils, escalation, fatigue d alerte"],
        ["SFAR / MAPAR / ACC / ACOG / NICE", "docs/clinical-references.md et docs/antecedents-context-catalog.md", "Scenarios et terrains patient"],
        ["KB runtime courte", "kb/postop-home-monitoring-signs.md", "Seule source injectee automatiquement dans les prompts runtime"],
        ["KB terrain guidance/sources", "kb/postop-terrain-context-guidance.md et kb/postop-terrain-context-sources.md", "Prepares pour plus tard mais non injectes automatiquement"],
    ]


def dependency_rows(ctx: AuditContext) -> list[list[str]]:
    rows: list[list[str]] = []
    for dep in ctx.backend_requirements:
        name = dep.split("==", 1)[0]
        rows.append(["Backend Python", name, dep])
    for name, version in sorted(ctx.frontend_package.get("dependencies", {}).items()):
        rows.append(["Frontend runtime", name, version])
    for name, version in sorted(ctx.frontend_package.get("devDependencies", {}).items()):
        rows.append(["Frontend dev", name, version])
    return rows


def core_file_rows() -> list[list[str]]:
    return [
        ["docker-compose.yml", "Assemble la stack et les healthchecks"],
        ["services/simulator/app/main.py", "Boucle de simulation et publication MQTT"],
        ["services/simulator/app/scenarios.py", "Moteur de trajectoire clinique"],
        ["config/simulation_scenarios.json", "Timelines, bruit, clamps, phases"],
        ["config/cases_catalog.json", "Cas cliniques, chirurgies, ponderations"],
        ["services/backend/app/main.py", "Composition des services FastAPI"],
        ["services/backend/app/mqtt/consumer.py", "Ingestion MQTT, alertes, Influx, WebSocket, ML samples"],
        ["services/backend/app/alerting/engine.py", "Moteur de regles et cooldown"],
        ["services/backend/app/ml/features.py", "Features, score immediat, score evolutif"],
        ["services/backend/app/ml/criticity_service.py", "Logistic regression et dataset runtime"],
        ["services/backend/app/routers/llm.py", "Clinical package, priorisation, cache, questionnaire"],
        ["services/backend/app/services/reports/clinical_report_service.py", "Assemblage metier du PDF patient"],
        ["services/backend/app/services/reports/pdf_renderer.py", "Rendu ReportLab du PDF patient"],
        ["services/frontend/src/pages/Patients.tsx", "Vue globale dashboard"],
        ["services/frontend/src/pages/PatientDetail.tsx", "Vue detail patient, IA, ML, questionnaire, export"],
    ]


def inactive_feature_rows() -> list[list[str]]:
    return [
        ["Antecedents medicaux chirurgicaux", "Latent", "PatientDetail.tsx construit un payload vide pour patient_factors/perioperative_context/free_text.", "La conduite a tenir basee sur le terrain n influence pas l analyse."],
        ["Route summaries", "Doublon", "Frontend appelle le clinical-package; getSummary/analyzeSummary restent exposes mais non utilises.", "Dette fonctionnelle et risque de divergence."],
        ["ScenarioControls.tsx", "Mort", "Composant defini mais non importe.", "Code a supprimer ou rebrancher."],
        ["Anomaly score dans l UI", "Partiel", "TrendResponse porte anomaly mais aucune carte front ne l affiche.", "README un peu plus ambitieux que le runtime."],
        ["KB terrain guidance/sources", "Dormant", "Les fichiers existent mais LocalKnowledgeBase lit seulement postop-home-monitoring-signs.md.", "Les sources terrain ne renforcent pas encore le prompt runtime."],
        ["probe_generation", "Dormant", "Methode presente dans OllamaClient mais non utilisee par /health.", "Le health peut etre optimiste."],
        ["history_default_hours", "Inutilise", "Setting charge mais non consomme par les routes.", "Variable sans effet runtime observable."],
    ]


def strengths() -> list[str]:
    return [
        "Architecture lisible pour une demo: simulateur, broker, backend, double stockage, frontend et LLM optionnel sont bien separes.",
        "Le simulateur est riche: baseline J0, phases, trends, instant jumps, bruit, clamps et delais d apparition.",
        "Le backend distingue regles, scoring, ML, LLM, exports et stockage de facon defendable.",
        "La couche PDF patient suit une bonne pratique routeur -> service -> renderer.",
        "La documentation clinique relie explicitement de nombreux choix a des sources reputees.",
        "La UX demo est forte: priorisation, notifications, questionnaire, export PDF et visualisation live.",
    ]


def weaknesses() -> list[str]:
    return [
        "Le projet depasse le sujet de base, mais au prix de plusieurs surfaces partiellement inactives ou en doublon.",
        "Une grande partie du raisonnement clinique repose sur des heuristiques codees en dur, pas sur des regles JSON homognes ni sur un modele appris robuste.",
        "Le modele ML apprend a partir de labels derives des alertes/thresholds, donc il reproduit surtout les biais du moteur expert.",
        "La securite reste celle d une demo: MQTT anonyme, aucune auth API, aucune gestion fine des roles.",
        "Le consumer MQTT backend n implemente pas les credentials alors que le simulateur les supporte deja.",
        "Le front n a pas de logique de reconnexion WebSocket, pas de tests, et plusieurs actions IA sont redondantes.",
    ]


def revision_priorities() -> list[list[str]]:
    return [
        ["P1", "Brancher vraiment le contexte patient", "Envoyer clinicalContextSelection dans buildAnalysisPayload et l integrer aux prompts et au PDF."],
        ["P1", "Supprimer les doublons d analyse", "Fusionner summary et clinical-package, retirer ou separer reellement les boutons IA."],
        ["P1", "Aligner les seuils SBP", "thresholds.sbp.critical=80 n est pas aligne avec la regle SBP_CRITICAL <=90."],
        ["P1", "Documenter le vrai statut du ML", "Presenter clairement le classifieur comme bonus demo supervise par labels derives."],
        ["P2", "Homogeneiser MQTT", "Ajouter MQTT_USERNAME/MQTT_PASSWORD au consumer backend et optionaliser un broker non anonyme."],
        ["P2", "Rendre visible ou retirer anomaly", "Soit ajouter une carte UI, soit retirer la promesse du README."],
        ["P2", "Ameliorer le WebSocket", "Ajouter reconnexion avec backoff et meilleure coherence de statut."],
        ["P2", "Rendre les builds deterministes", "Ajouter package-lock.json et preferer npm ci."],
        ["P3", "Etendre la KB runtime", "Injecter la guidance terrain/context et pas seulement un extrait statique court."],
        ["P3", "Persister plus de metadonnees patient", "Age, baseline, notes et scenario actif meritent une persistence explicite."],
    ]


def generate_markdown(ctx: AuditContext) -> str:
    lines = [
        "# Home Track - Audit technique complet",
        "",
        f"- Date de generation: {ctx.generated_at}",
        f"- Comparaison au sujet: {SPEC_PDF}",
        "- Repository analyse: postop-monitoring",
        "",
        "## Verdict",
        "",
        "- Le projet couvre les 7 must-have du PDF projet et va nettement au-dela du brief initial.",
        "- Son point fort est la chaine de donnees complete et demo-friendly.",
        "- Son principal point faible est la presence de fonctions en doublon ou seulement partiellement branchees.",
        "",
        "## Ecarts majeurs",
        "",
        "- Le panneau Antecedents medicaux chirurgicaux est visible mais non injecte dans le payload d analyse IA.",
        "- Le score anomaly existe cote backend mais pas dans l interface.",
        "- Le modele ML est surtout une surcouche de demonstration appuyee sur des labels derives du moteur de regles.",
        "",
    ]
    lines.append("## Conformite")
    lines.append("")
    for row in spec_rows(ctx):
        lines.append(f"- {row[0]} | {row[1]} | {row[2]} | preuve: {row[3]}")
    lines.append("")
    lines.append("## Priorites")
    lines.append("")
    for row in revision_priorities():
        lines.append(f"- {row[0]} {row[1]}: {row[2]}")
    lines.append("")
    return "\n".join(lines)


def build_story(ctx: AuditContext, styles: StyleSheet1, doc: SimpleDocTemplate) -> list[Any]:
    width = doc.width
    story: list[Any] = []
    story.append(Paragraph("Home Track - audit technique complet du projet", styles["ReportTitle"]))
    story.append(
        Paragraph(
            "Architecture, simulateur, ponderations, stockage, alertes, ML, LLM, frontend, PDF et comparaison au sujet Epitech.",
            styles["ReportSubtitle"],
        )
    )
    story.append(
        paragraph_block(
            "Cadre de comparaison",
            [
                f"Date de generation: {ctx.generated_at}",
                f"PDF sujet compare: {SPEC_PDF}",
                "Sujet extrait: Projet 1 - Monitoring post-operatoire a domicile, module IoT / Sante / Intelligence Artificielle, Epitech MBA1, 4 mars 2026.",
                "Verdict global: le projet couvre les 7 must-have et depasse largement le perimetre du brief.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(section_header("Synthese executive", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(bullet_panel("Ce que le projet fait bien", strengths(), width, styles, tone="good"))
    story.append(Spacer(1, 3 * mm))
    story.append(bullet_panel("Ce qui limite aujourd hui le projet", weaknesses(), width, styles, tone="warn"))

    story.append(PageBreak())
    story.append(section_header("Comparaison au cahier des charges Epitech", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        generic_table(
            ["Exigence", "Statut", "Lecture technique", "Preuve principale"],
            spec_rows(ctx),
            [40 * mm, 18 * mm, 80 * mm, 48 * mm],
            styles,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(generic_table(["Bonus", "Statut", "Commentaire"], bonus_rows(), [45 * mm, 20 * mm, 115 * mm], styles))

    story.append(PageBreak())
    story.append(section_header("Architecture globale et flux de donnees", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        generic_table(
            ["Service", "Role", "Image/build", "Port", "Notes"],
            service_rows(),
            [22 * mm, 30 * mm, 42 * mm, 16 * mm, 70 * mm],
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        paragraph_block(
            "Flux runtime reel",
            [
                "1. Le simulateur charge les patients seed, choisit des cas cliniques, reconstruit un historique J0 -> maintenant puis publie le live via MQTT.",
                "2. Mosquitto relaie les messages patients/{id}/vitals au consumer backend, et recoit aussi le topic de controle simulator/control/refresh.",
                "3. Le consumer backend valide, derive MAP et shock index, pousse l etat en memoire, evalue les alertes, ecrit Influx/Postgres, enregistre un sample ML et broadcast en WebSocket.",
                "4. Le frontend React consomme REST pour les vues initiales et WebSocket pour le flux live.",
                "5. Le LLM via Ollama est optionnel. En absence de modele disponible, l API renvoie un fallback rule-based structure.",
                "6. L export PDF patient passe par un service d assemblage clinique puis un renderer ReportLab separe.",
            ],
            width,
            styles,
        )
    )

    story.append(PageBreak())
    story.append(section_header("Simulateur clinique", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        paragraph_block(
            "Fonctionnement",
            [
                "Le simulateur est pilote par simulation_scenarios.json pour la dynamique et cases_catalog.json pour les cas cliniques, les chirurgies plausibles et les jours post-op.",
                "PAT-001 reste le patient temoin sain lors des refresh. Les autres slots tirent des cas dynamiques coherents.",
                "Le moteur utilise target_shift, trend_per_10min, adaptation_rate, instant_jump, onset_delay_range_minutes, repeat_timeline, initial_shift_by_postop_day et rebleed_pattern.",
                "Le backfill historique est publie avant le live: pas de simple instantane, mais une trajectoire reconstruite depuis J0.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(generic_table(["Ponderation chirurgie", "Poids", "Usage"], simulator_weight_rows(ctx), [45 * mm, 25 * mm, 110 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(bullet_panel("Catalogue de cas cliniques", scenario_case_bullets(ctx), width, styles))
    story.append(Spacer(1, 3 * mm))
    story.append(bullet_panel("Catalogue de scenarios et primitives temporelles", scenario_engine_bullets(ctx), width, styles))
    story.append(Spacer(1, 3 * mm))
    story.append(
        generic_table(
            ["Bruit / clamp", "Valeur", "Interpretation"],
            [
                ["hr_sd", "1.4 bpm", "Variabilite naturelle FC"],
                ["spo2_sd", "0.5 pt", "Bruit modere SpO2"],
                ["sbp_sd / dbp_sd", "2.2 / 1.8 mmHg", "Bruit tensionnel de demo"],
                ["rr_sd", "0.8 /min", "Variabilite FR"],
                ["temp_sd", "0.05 C", "Temperature tres stable par defaut"],
                ["Clamp", "HR 40-180, SpO2 75-100, SBP 60-200, DBP 35-130, RR 8-40, T 35-41", "Bornes de securite pour garder des valeurs plausibles"],
            ],
            [40 * mm, 38 * mm, 102 * mm],
            styles,
        )
    )

    story.append(PageBreak())
    story.append(section_header("MQTT et broker Mosquitto", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        paragraph_block(
            "Parametrage actuel",
            [
                "Topic principal: patients/{patient_id}/vitals.",
                "Topic de controle: simulator/control/refresh.",
                "QoS: 1 cote simulator et backend.",
                "Broker demo: listener 1883, allow_anonymous=true, persistence=false.",
                "Le simulateur supporte MQTT_USERNAME/MQTT_PASSWORD, mais le consumer backend ne configure pas de credentials.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        bullet_panel(
            "Implications",
            [
                "Tres bien pour la demo: faible friction et flux simples a expliquer.",
                "Pas suffisant pour un environnement reel: pas d auth, pas de persistence broker, pas de TLS.",
                "Le backend publie aussi des commandes de refresh au simulateur via le meme broker.",
            ],
            width,
            styles,
            tone="warn",
        )
    )

    story.append(PageBreak())
    story.append(section_header("Stockage et modele de donnees", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        generic_table(
            ["Couche", "Contenu", "Observation"],
            [
                ["InfluxDB", "Measurement vitals", "Fields: hr, spo2, sbp, dbp, map, rr, temp, shock_index, postop_day"],
                ["InfluxDB", "Tags", "patient_id et profile seulement; scenario/chirurgie ne sont pas tags de serie"],
                ["PostgreSQL", "patients", "id, full_name, profile, surgery_type, postop_day, risk_level, room, history_json"],
                ["PostgreSQL", "alerts", "alertes actives et historiques avec metric_snapshot JSONB"],
                ["PostgreSQL", "notes", "resumes et notes de synthese"],
                ["PostgreSQL", "llm_analysis_cache", "cache JSON du clinical package + questionnaire + etat resting/stale"],
                ["PostgreSQL", "feedback_ml", "annotations de validation/invalidation ML"],
                ["PostgreSQL", "notifications", "centre de notifications in-app et navigateur"],
            ],
            [28 * mm, 45 * mm, 107 * mm],
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        bullet_panel(
            "Limites de persistence",
            [
                "age, baseline et notes du cases_catalog ne sont pas persistes dans la table patients.",
                "Le scenario actif vit surtout dans last_vitals, alerts et payloads, pas comme colonne relationnelle stable.",
                "AlertState est purement en memoire: les fenetres de tendance/duree sont perdues en cas de restart backend.",
                "L historique complet hours=0 est pratique pour la demo mais pas optimal pour une grosse volumetrie.",
            ],
            width,
            styles,
            tone="warn",
        )
    )

    story.append(PageBreak())
    story.append(section_header("Systeme d alertes et incertitude", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(generic_table(["Metrique", "Info", "Warning", "Critical"], alert_threshold_rows(ctx), [33 * mm, 32 * mm, 32 * mm, 73 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(
        paragraph_block(
            "Logique d evaluation",
            [
                f"Nombre de regles: {len(ctx.alert_rules.get('rules', []))} (INFO={ctx.rule_levels.get('INFO', 0)}, WARNING={ctx.rule_levels.get('WARNING', 0)}, CRITICAL={ctx.rule_levels.get('CRITICAL', 0)}).",
                "Le moteur supporte all/any imbriques, seuil instantane, seuil sur duree et trend delta sur fenetre glissante.",
                "Le cooldown par defaut est de 60 secondes, avec un etat in-memory par patient et regle.",
                "Chaque alerte est enrichie par un payload d incertitude: evidence_mode, risque de faux positif, risque de faux negatif, et delai de remesure conseille.",
                "Le backfill historique enregistre les alertes comme historiques sans les re-broadcaster comme si elles etaient live.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        bullet_panel(
            "Point de coherence a corriger",
            [
                "thresholds.sbp.critical vaut 80 mmHg, mais la regle SBP_CRITICAL declenche deja a 90 mmHg.",
                "Cette discordance complique la lecture croisee entre alertes, score immediat et interpretation clinique.",
            ],
            width,
            styles,
            tone="risk",
        )
    )

    story.append(PageBreak())
    story.append(section_header("ML et scoring clinique", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        paragraph_block(
            "Ce que le projet appelle modele",
            [
                "1. Le simulateur n est pas un modele appris: c est un generateur mecaniste base sur des regles et des trajectoires cliniques codees.",
                "2. L anomaly service est un IsolationForest re-entraine a la volee sur l historique courant du patient; il n est ni persiste ni affiche dans l UI.",
                "3. Le vrai modele supervise est un LogisticRegression + StandardScaler entrainable en runtime sur vitals.csv + labeled_feedback.csv.",
                "4. Le composant qui pese le plus fort dans l experience actuelle reste en pratique le scoring expert compute_immediate_criticality + compute_evolving_risk.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(generic_table(["Immediate criticality", "Points", "Sens"], immediate_criticality_rows(), [58 * mm, 28 * mm, 94 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(generic_table(["Explanatory score", "Points", "Usage"], explanatory_score_rows(), [62 * mm, 28 * mm, 90 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(generic_table(["Famille scenario", "Signaux dominants", "Penalites", "Cap"], evolving_risk_rows(), [40 * mm, 75 * mm, 45 * mm, 18 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(
        bullet_panel(
            "Lecture critique du ML",
            [
                "Le pipeline appris utilise 16 features: instantane courant + derive depuis J0 + minima/maxima de trajectoire.",
                "La cible has_critical est derivee de regles threshold/alert_count, pas d un gold standard clinique annote.",
                "Le modele apprend donc surtout une projection compacte du moteur expert deja existant.",
                "Pour une soutenance, il faut le presenter comme bonus data science coherent, pas comme aide diagnostique fiable.",
            ],
            width,
            styles,
            tone="warn",
        )
    )

    story.append(PageBreak())
    story.append(section_header("LLM, questionnaire et sources cliniques", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        paragraph_block(
            "Construction reelle de la couche IA",
            [
                "Le LLM n est pas entraine dans le projet. Il s agit d un modele externe pre-entraine (qwen2.5:7b-instruct) servi localement par Ollama.",
                "La personnalisation repose sur des prompts systemes stricts, des schemas JSON, un fallback rule-based et un cache patient/fingerprint.",
                "Le questionnaire differentiel selectionne jusqu a 3 modules a partir des alertes, vitaux et deltas historiques, puis genere des hints ponderes de 1 a 4.",
                "Le clinical package peut passer en mode resting apres validation du questionnaire, puis devenir stale si une derive clinique depasse les delta triggers.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(generic_table(["Mecanisme", "Detail", "Preuve"], questionnaire_weight_rows(), [45 * mm, 75 * mm, 60 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(generic_table(["Base source", "Ou", "Ce que ca soutient"], clinical_source_rows(), [34 * mm, 70 * mm, 76 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(
        bullet_panel(
            "Ecarts entre documentation et runtime",
            [
                "Le projet documente abondamment ARISCAT, Caprini, RCRI, NEWS2, SFAR, MAPAR, NICE, WHO, CNIL et d autres sources.",
                "En runtime, le LocalKnowledgeBase ne renvoie pourtant qu un extrait court de postop-home-monitoring-signs.md.",
                "Les fichiers postop-terrain-context-guidance.md et postop-terrain-context-sources.md sont preparatoires; ils ne sont pas encore injectes automatiquement.",
                "Le health endpoint verifie la presence du service et du modele, mais pas une generation reelle. probe_generation existe sans etre utilise.",
            ],
            width,
            styles,
            tone="warn",
        )
    )

    story.append(PageBreak())
    story.append(section_header("Frontend et UX operative", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        paragraph_block(
            "Flux UI reel",
            [
                "La page Patients charge patients + alertes par REST puis applique les updates live via WebSocket.",
                "La page PatientDetail combine vitaux, historique, alertes actives/historiques, questionnaire, score ML, clinical package et export CSV/PDF.",
                "Le centre de notifications est global a l application et peut utiliser la Notification API du navigateur.",
                "Les types frontend sont riches et couvrent anomaly, questionnaire, cache LLM, priorisation et feedback ML.",
            ],
            width,
            styles,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        bullet_panel(
            "Limites front a expliquer",
            [
                "Le panneau Antecedents medicaux chirurgicaux est visible mais non pris en compte par buildAnalysisPayload.",
                "Le WebSocket envoie un heartbeat mais n a pas de reconnexion/backoff robuste.",
                "Le bouton Actualiser le resume recharge aujourd hui la meme source que Actualiser l analyse.",
                "Aucun test frontend n est present dans le repository.",
            ],
            width,
            styles,
            tone="warn",
        )
    )

    story.append(PageBreak())
    story.append(section_header("Export PDF patient", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(
        paragraph_block(
            "Bonne pratique actuellement appliquee",
            [
                "Le routeur export est fin: il assemble le payload clinique puis appelle le renderer.",
                "clinical_report_service.py concentre l aggregation metier: patient, vitaux, baseline, alertes, analyses avant/apres questionnaire, terrain guidance et contingency points.",
                "pdf_renderer.py concentre le layout ReportLab, l entete Home Track et la pagination.",
                "Cette separation est une bonne base pour faire evoluer le PDF sans gonfler la route HTTP.",
            ],
            width,
            styles,
        )
    )

    story.append(PageBreak())
    story.append(section_header("Fonctions inactives, partielles ou dormantes", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(generic_table(["Element", "Etat", "Preuve", "Impact"], inactive_feature_rows(), [42 * mm, 25 * mm, 62 * mm, 51 * mm], styles))

    story.append(PageBreak())
    story.append(section_header("Revision de code recommandee", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(generic_table(["Priorite", "Sujet", "Action recommande"], revision_priorities(), [16 * mm, 52 * mm, 112 * mm], styles))

    story.append(PageBreak())
    story.append(section_header("Dependances et empreinte technique", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(generic_table(["Famille", "Nom", "Version / spec"], dependency_rows(ctx), [34 * mm, 52 * mm, 94 * mm], styles))

    story.append(PageBreak())
    story.append(section_header("Annexe - fichiers coeur du projet", width, styles))
    story.append(Spacer(1, 2 * mm))
    story.append(generic_table(["Fichier", "Role"], core_file_rows(), [70 * mm, 110 * mm], styles))
    story.append(Spacer(1, 3 * mm))
    story.append(
        paragraph_block(
            "Niveau de couverture de tests",
            [
                f"Tests backend detectes: {ctx.test_count}.",
                "Les tests couvrent surtout les regles, les endpoints API, le PDF, le fallback LLM et plusieurs re-rankings par scenario.",
                "Il n y a pas de tests frontend ni de test end-to-end versionne dans le repository.",
            ],
            width,
            styles,
        )
    )
    return story


def draw_page_chrome(canvas, doc, generated_at: str) -> None:
    _page_width, page_height = A4
    canvas.saveState()
    canvas.setFillColor(REPORT_BLUE)
    canvas.rect(doc.leftMargin, page_height - 17 * mm, doc.width, 8 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(doc.leftMargin + 3 * mm, page_height - 13.4 * mm, "Home Track | Audit technique complet")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(doc.leftMargin + doc.width - 3 * mm, page_height - 13.4 * mm, f"Genere le {generated_at}")
    canvas.setFillColor(REPORT_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(doc.leftMargin, 9 * mm, "Repository: postop-monitoring")
    canvas.drawRightString(doc.leftMargin + doc.width, 9 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def render_pdf(ctx: AuditContext) -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=24 * mm,
        bottomMargin=14 * mm,
        title="Home Track architecture audit",
        author="OpenAI Codex",
        pageCompression=0,
    )
    story = build_story(ctx, styles, doc)
    doc.build(
        story,
        onFirstPage=lambda canvas, pdf_doc: draw_page_chrome(canvas, pdf_doc, ctx.generated_at),
        onLaterPages=lambda canvas, pdf_doc: draw_page_chrome(canvas, pdf_doc, ctx.generated_at),
    )


def main() -> None:
    ctx = build_context()
    OUTPUT_MD.write_text(generate_markdown(ctx), encoding="utf-8")
    render_pdf(ctx)
    print(OUTPUT_PDF)
    print(OUTPUT_MD)


if __name__ == "__main__":
    main()
