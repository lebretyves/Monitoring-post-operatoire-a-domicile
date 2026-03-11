from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = Path("/app/runtime") if Path("/app/runtime").exists() else ROOT / "runtime"
OUTPUT_PDF = RUNTIME_DIR / "architecture-postop-monitoring.pdf"


def section_title(text: str, styles):
    return Table(
        [[Paragraph(f"<b>{text}</b>", styles["SectionTitle"])]],
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


def service_table(styles):
    rows = [
        ["Service", "Role principal"],
        ["frontend", "Dashboard React/Vite, pages Patients et Detail, WebSocket, notifications navigateur"],
        ["backend", "FastAPI, ingestion MQTT, regles d alertes, REST, WebSocket, ML, LLM, export, push"],
        ["simulator", "Generation des constantes patient selon scenarios et refresh de population"],
        ["mosquitto", "Broker MQTT pour patients/{id}/vitals et refresh simulator"],
        ["influxdb", "Historique temps reel des constantes vitales"],
        ["postgres", "Patients, alertes, notifications, feedback ML, cache d analyse, push subscriptions"],
        ["ollama", "Inference locale du modele qwen2.5:7b-instruct"],
    ]
    table = Table(rows, colWidths=[38 * mm, 142 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def architecture_flow() -> str:
    return """Utilisateur / Navigateur
        |
        v
Frontend React/Vite
  - PatientsPage
  - PatientDetailPage
  - NotificationCenter
        |
        +--> REST --> Backend FastAPI
        |
        +--> WebSocket /ws/live --> flux temps reel
        |
        +--> Service Worker --> Web Push

Simulator Python
  - patients_seed.json
  - cases_catalog.json
  - simulation_scenarios.json
        |
        v
Mosquitto MQTT
  - patients/{id}/vitals
  - simulator/refresh
        |
        v
Backend FastAPI
  - MQTTConsumer
  - AlertEngine
  - ML criticite
  - LLM / questionnaire / categories
  - export PDF / CSV
  - notifications + push
        |
        +--> InfluxDB : historique vital
        |
        +--> PostgreSQL : relationnel / cache / feedback
        |
        +--> runtime/ml : vitals.csv / labeled_feedback.csv / model.pkl
        |
        +--> Ollama : generation LLM locale
        |
        +--> Frontend : REST + WebSocket + push"""


def build_pdf() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
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
    styles.add(
        ParagraphStyle(
            name="MonoBlock",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8.4,
            leading=10,
            leftIndent=6,
            rightIndent=6,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#eff6ff"),
            borderColor=colors.HexColor("#bfdbfe"),
            borderWidth=0.6,
            borderPadding=8,
            borderRadius=4,
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title="Architecture complete - Postop Monitoring",
        author="OpenAI Codex",
    )

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    story = [
        Paragraph("Architecture complete du projet", styles["CoverTitle"]),
        Spacer(1, 4 * mm),
        Paragraph("Projet: Monitoring post operatoire a domicile", styles["Body"]),
        Paragraph(f"Genere le: {now}", styles["Body"]),
        Spacer(1, 6 * mm),
        Paragraph(
            "Ce document resume l architecture technique reelle du depot: services Docker, flux de donnees, "
            "backend, frontend, simulateur, stockage, ML, LLM, exports et notifications.",
            styles["Body"],
        ),
        Spacer(1, 6 * mm),
    ]

    story.append(section_title("1. Vue d ensemble", styles))
    story += bullet_lines(
        [
            "Architecture en micro services Docker relies par MQTT, REST, WebSocket et web push.",
            "Le simulateur publie les constantes, le backend les consomme, calcule les alertes et sert le front.",
            "InfluxDB stocke les series temporelles; PostgreSQL stocke le relationnel et la trace clinique.",
            "Le ML estime la criticite; le LLM structure l explication et la conduite a tenir.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("2. Services Docker", styles))
    story.append(service_table(styles))
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("3. Schema des flux", styles))
    story.append(Preformatted(architecture_flow(), styles["MonoBlock"]))
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("4. Flux temps reel", styles))
    story += bullet_lines(
        [
            "Le simulator construit les cas a partir des fichiers config et publie les vitals sur MQTT.",
            "Le MQTTConsumer du backend normalise la mesure, ecrit InfluxDB et pousse l etat dans AlertState.",
            "L AlertEngine applique les regles et cree les alertes puis les notifications.",
            "Le backend diffuse ensuite vitals, alertes et notifications au frontend via WebSocket.",
            "Le service web push peut envoyer une notification navigateur hors page active si une souscription existe.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("5. Backend FastAPI", styles))
    story += bullet_lines(
        [
            "Entree principale: app/main.py avec lifespan, wiring des services et healthchecks.",
            "Routers metier: patients, alerts, trends, ml, llm, export, notifications, push.",
            "Modules internes: alerting, mqtt, storage, ws, ml, llm, services/reports.",
            "Le backend orchestre a la fois la logique temps reel, la logique clinique et les exports.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("6. Stockage", styles))
    story += bullet_lines(
        [
            "InfluxDB conserve l historique des constantes et sert les vues 1h, 6h, 24h et depuis J0.",
            "PostgreSQL conserve les patients, alertes, notes, cache LLM, feedback ML, notifications et push_subscriptions.",
            "Le dossier runtime/ml conserve le dataset d entrainement et le modele de criticite sauvegarde.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("7. ML et LLM", styles))
    story += bullet_lines(
        [
            "ML criticite: LogisticRegression sur vitals et derivees temporelles, entrainee via /api/ml/train.",
            "Le ML sert surtout au score de criticite, pas au diagnostic texte libre.",
            "LLM Ollama: generation JSON structuree pour hypotheses, synthese, questionnaire et conduite a tenir.",
            "Le LLM est utilise avec fallback rule based, categories normalisees et garde fous de stabilite.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("8. Frontend React", styles))
    story += bullet_lines(
        [
            "Deux vues principales: liste population et fiche patient detaillee.",
            "Le front consomme les routes REST pour patients, tendances, ML, LLM, exports et validation.",
            "Le live arrive par WebSocket et met a jour les notifications en temps reel.",
            "Le service worker permet le web push quand une souscription a ete enregistree.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("9. Exports et trace clinique", styles))
    story += bullet_lines(
        [
            "Export CSV pour l historique du patient.",
            "Export PDF clinique compose a partir des constantes, alertes, analyse clinique, questionnaire et validation medecin.",
            "La validation medicale peut maintenant remonter avec son commentaire dans le PDF.",
        ],
        styles,
    )
    story.append(Spacer(1, 4 * mm))

    story.append(section_title("10. Fichiers de configuration clefs", styles))
    story += bullet_lines(
        [
            "docker-compose.yml pour la stack complete.",
            "config/alert_rules.json pour les regles d alertes.",
            "config/simulation_scenarios.json pour les trajectoires physiologiques.",
            "config/cases_catalog.json pour les cas cliniques et contextes.",
            "config/patients_seed.json pour la population de base.",
            "config/questionnaire_rules.json pour le questionnaire differentiel.",
        ],
        styles,
    )

    doc.build(story)
    return OUTPUT_PDF


if __name__ == "__main__":
    pdf_path = build_pdf()
    print(pdf_path)
