from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = Path("/app/runtime") if Path("/app/runtime").exists() else ROOT / "runtime"
OUTPUT_PDF = RUNTIME_DIR / "expose-ultra-complet-postop-monitoring.pdf"


def section_title(text: str, styles):
    return Table(
        [[Paragraph(f"<b>{text}</b>", styles["SectionTitle"]) ]],
        colWidths=[180 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f3d66")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        ),
    )


def bullet_lines(items: list[str], styles):
    return [Paragraph(f"- {item}", styles["Body"]) for item in items]


def build_pdf() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=28,
            textColor=colors.HexColor("#0f172a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=2,
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title="Cahier ultra complet - Postop Monitoring",
        author="GitHub Copilot",
    )

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    story = [
        Paragraph("Cahier Ultra Complet", styles["CoverTitle"]),
        Spacer(1, 4 * mm),
        Paragraph("Projet: Monitoring post-operatoire a domicile", styles["Body"]),
        Paragraph(f"Date: {now}", styles["Body"]),
        Spacer(1, 6 * mm),
        Paragraph(
            "Document de synthese pour presentation: architecture, dependances, flux de donnees, roles des modules, IA/ML/LLM, "
            "forces/faiblesses, benchmark et roadmap.",
            styles["Body"],
        ),
        Spacer(1, 6 * mm),
    ]

    story.append(section_title("1. Resume executif", styles))
    story += bullet_lines(
        [
            "Plateforme complete de monitoring clinique temps reel orientee demo et explicabilite.",
            "Pipeline bout en bout: simulation -> MQTT -> backend -> stockage -> frontend -> export/notification.",
            "Approche hybride: regles deterministes pour securite + ML pour criticite + LLM pour explication.",
            "Objectif: assistance clinique prudente, pas diagnostic autonome.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("2. Architecture technique", styles))
    story += bullet_lines(
        [
            "Simulator Python: genere des constantes vitales scenario-driven (J0 -> J3).",
            "Mosquitto MQTT: transport telemetry QoS 1.",
            "Backend FastAPI: ingestion, alerting, scoring, API REST, WebSocket live.",
            "InfluxDB: series temporelles vitales.",
            "PostgreSQL: patients, alertes, notifications, feedback ML, cache analyses.",
            "Frontend React/Vite: cockpit patient et vue population.",
            "Ollama local: generation LLM avec fallback rule-based.",
            "Web Push: notifications systeme via service worker + abonnement backend.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("3. Activation des fonctions (flags)", styles))
    story += bullet_lines(
        [
            "ENABLE_LLM: active les routes LLM sur Ollama; sinon fallback local explicite.",
            "ENABLE_ML: active scoring/entrainement criticite.",
            "ENABLE_WEBPUSH: active abonnement push + dispatch hors page active.",
            "APP_TEST_MODE: stockage memoire et mode tests.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("4. ML, LM, LLM: roles et entrainement", styles))
    story += bullet_lines(
        [
            "ML (LogisticRegression): probabilite de criticite a partir des constantes et derivees temporelles.",
            "Donnees ML: runtime/ml/vitals.csv + runtime/ml/labeled_feedback.csv.",
            "Entrainement ML: manuel via endpoint /api/ml/train.",
            "LLM (Ollama Qwen): generation JSON structuree (resume, hypotheses, conduite a tenir).",
            "LLM non entraine dans ce projet: uniquement inference locale + prompts + schema validation.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("5. Algorithmes simulateur et cas cliniques", styles))
    story += bullet_lines(
        [
            "Simulation par phases: trend, instant jump, target shift, bruit et contraintes physiologiques.",
            "Cas progressifs et cas brutaux avec delai d'apparition configurable.",
            "Refresh demo: 1 patient temoin sain + 4 cas pathologiques tires selon ponderations.",
            "Historique reconstruit depuis J0 pour visualisation trajectoire.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("6. Qualites du projet", styles))
    story += bullet_lines(
        [
            "Architecture lisible et pedagogique, demontrable en temps reel.",
            "Separation claire des responsabilites (simu / backend / frontend / stockage).",
            "Robustesse fonctionnelle grace aux fallbacks (LLM et notifications).",
            "Workflow clinique structurant avec validation medecin avant conduite a tenir.",
            "Exports CSV/PDF et trace documentaire directement exploitables en demo.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("7. Defauts et risques", styles))
    story += bullet_lines(
        [
            "Complexite elevee sur la page PatientDetail (risque de maintenance).",
            "Notifications hors navigateur dependantes de Firefox/Windows runtime.",
            "MLOps encore limit: pas de registry modele ni monitoring de drift.",
            "Conformite securite/identite non industrialisee (auth/RBAC/audit a renforcer).",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("8. Benchmark externe (positionnement)", styles))
    story += bullet_lines(
        [
            "ThingsBoard: excellent socle IoT generique (protocoles, rule engine, dashboards, multi-tenant).",
            "Home Assistant: fort en automatisation locale et ecosysteme d'integrations.",
            "Differenciation du projet: vertical clinique post-op avec validation medecin + conduite a tenir IA + export medical.",
            "Nuance: impossible d'affirmer objectivement que personne ne fait equivalent; la combinaison actuelle reste tres differenciante pour un projet academique/POC.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("9. Roadmap et ouvertures", styles))
    story += bullet_lines(
        [
            "Court terme: fiabiliser notifications 24/7 via agent desktop optionnel.",
            "Moyen terme: durcissement securite (authn/authz), audit trail, governance data.",
            "Moyen terme: pipeline MLOps (validation continue, versioning, metriques).",
            "Long terme: evaluations terrain et protocoles cliniques supervises.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("10. Conclusion de soutenance", styles))
    story += bullet_lines(
        [
            "Le projet est une base solide de telemonitoring intelligent, claire, modulaire et demonstrable.",
            "La securite immediate repose sur des regles deterministes, l'IA etant explicative et encadree.",
            "La trajectoire future est nette: industrialisation, securite, MLOps et validation terrain.",
        ],
        styles,
    )

    doc.build(story)
    return OUTPUT_PDF


if __name__ == "__main__":
    output = build_pdf()
    print(str(output))
