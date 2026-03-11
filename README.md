# Monitoring post-operatoire a domicile

Projet MBA1 Epitech de monitoring post-operatoire a domicile.

Le projet simule plusieurs patients, envoie leurs constantes via MQTT, applique des regles d'alerte, calcule un score ML de criticite, produit une analyse clinique assistee par LLM, puis expose le tout dans un dashboard web temps reel.

## Objectif

- simuler un suivi post-operatoire multi-patients
- visualiser les constantes et alertes en temps reel
- aider l'orientation clinique avec une logique hybride
- fournir un support de demo simple a lancer

La logique reste volontairement hybride:

- regles cliniques pour les seuils et alertes critiques
- ML pour le score longitudinal de criticite
- LLM pour la synthese, les hypotheses et la conduite a tenir

## Stack

- Simulator Python + `paho-mqtt`
- Mosquitto pour MQTT
- FastAPI pour REST + WebSocket
- InfluxDB pour l'historique des constantes
- PostgreSQL pour les patients, alertes, cache d'analyse, notifications et feedback ML
- React + Vite pour le dashboard
- `IsolationForest` pour le bonus anomalies
- Ollama local avec `qwen2.5:7b-instruct` pour le bonus LLM

## Demarrage principal

Le lancement principal du projet se fait avec [`start.sh`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\start.sh).

Ce script:

- verifie `docker`
- cree `.env` depuis `.env.example` si besoin
- valide `docker compose`
- construit et demarre toute la stack
- attend que le backend et le frontend soient joignables

Commande:

```bash
cd /c/Users/lebre/Desktop/Monitoring/postop-monitoring
NO_BROWSER=1 ./start.sh
```

Le script a ete verifie: il fonctionne bien dans un terminal Bash/Git Bash.

## Alternative Windows

Si vous utilisez PowerShell ou Terminal Windows, utilisez plutot [`start-demo.ps1`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\start-demo.ps1):

```powershell
cd c:\Users\lebre\Desktop\Monitoring\postop-monitoring
.\start-demo.ps1
```

Alternative double-clic / Windows:

```bat
start-demo.cmd
```

## URLs utiles

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/health`
- InfluxDB: `http://localhost:8086`
- PostgreSQL: `localhost:5432`
- Mosquitto MQTT: `localhost:1883`

## Schema d'architecture

```mermaid
flowchart LR
    U[Utilisateur]
    FE[Frontend React + Vite]
    SW[Service Worker / Web Push]
    WS[WebSocket live]
    API[Backend FastAPI]
    MQTT[Broker Mosquitto]
    SIM[Simulator Python]
    INF[(InfluxDB)]
    PG[(PostgreSQL)]
    ML[ML criticite]
    LLM[Ollama<br/>qwen2.5:7b-instruct]
    PDF[Exports CSV / PDF]

    U --> FE
    FE -->|REST| API
    API -->|JSON| FE
    API --> WS
    WS --> FE
    FE --> SW

    SIM -->|patients/{id}/vitals| MQTT
    API -->|refresh demo| MQTT
    MQTT --> API

    API --> INF
    API --> PG
    API --> ML
    API --> LLM
    API --> PDF
```

## Lecture de l'architecture

- le simulateur genere les constantes de plusieurs patients a partir des scenarios
- il publie les constantes sur MQTT
- le backend consomme les messages, stocke l'historique, applique les regles d'alerte et diffuse le live
- le front affiche le tableau de bord, les graphes, les hypotheses et les scores
- le ML apprend la criticite a partir des vitals et feedbacks
- le LLM reformule l'analyse clinique et la conduite a tenir
- le PDF synthese le cas clinique exporte

## Services Docker

- `simulator`: simulation des cas cliniques
- `mosquitto`: broker MQTT
- `backend`: API, regles, ML, LLM, PDF, WebSocket
- `frontend`: dashboard React
- `postgres`: stockage relationnel
- `influxdb`: historique des constantes
- `ollama`: serveur local LLM

## Fonctionnement clinique

L'interface distingue plusieurs blocs:

- `Criticite immediate`: danger instantane base sur les seuils et alertes du moment
- `Risque evolutif`: derive clinique observee depuis `J0`
- `Score ML historique`: score appris a partir de la trajectoire du patient
- `Analyse clinique IA`: synthese structuree produite par le backend via LLM + fallback local

Important:

- le simulateur ne change pas a cause du contexte patient ou de la validation medicale
- le LLM n'est pas reentraine localement
- la validation medicale met a jour l'analyse clinique
- l'entrainement ML reste une action separee

## Schema fonctionnel

```mermaid
flowchart TD
    V[Vitals + historique + alertes]
    R[Regles cliniques]
    E[Risque evolutif]
    M[Modele ML de criticite]
    Q[Questionnaire differentiel]
    D[Validation medicale]
    L[Analyse clinique IA]
    T[Conduite a tenir]
    P[Export PDF]

    V --> R
    V --> E
    V --> M
    V --> L
    Q --> L
    D --> L
    D --> T
    L --> T
    L --> P
    T --> P
```

## Organisation des fonctions

Le backend se repartit en couches distinctes.

- `Ingestion temps reel`
  - recoit les constantes MQTT
  - met a jour l'etat patient, l'historique et les alertes
  - fichiers: [`consumer.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\mqtt\consumer.py), [`engine.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\alerting\engine.py)

- `Regles et criticite immediate`
  - detecte les seuils franchis et les alertes composites
  - alimente les alertes `INFO / WARNING / CRITICAL`
  - fichiers: [`engine.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\alerting\engine.py), [`alert_rules.json`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\alert_rules.json)

- `ML de criticite`
  - construit les features de trajectoire
  - enregistre `vitals.csv` et `labeled_feedback.csv`
  - entraine `model.pkl`
  - calcule le `Score ML historique`
  - fichiers: [`criticity_service.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\ml\criticity_service.py), [`features.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\ml\features.py), [`ml.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\ml.py)

- `Analyse clinique IA`
  - construit le `clinical-package`
  - fusionne vitals, historique, alertes, questionnaire, validation medicale et KB locale
  - appelle le LLM si disponible, sinon fallback `rule-based`
  - fichiers: [`llm.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\llm.py), [`prompt_templates.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\llm\prompt_templates.py), [`validated_categories.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\llm\validated_categories.py), [`kb.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\llm\kb.py)

- `Questionnaire differentiel`
  - choisit les modules de questions selon le tableau clinique
  - renvoie des indices pour reorienter les hypotheses
  - fichiers: [`questionnaire.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\llm\questionnaire.py), [`questionnaire_rules.json`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\questionnaire_rules.json)

- `Validation medicale`
  - enregistre le diagnostic final et le commentaire
  - bascule l'analyse du mode `pre-validation` au mode `post-validation`
  - ne reentraine pas automatiquement le modele ML
  - fichiers: [`ml.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\ml.py), [`postgres.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\storage\postgres.py)

- `Conduite a tenir`
  - genere une guidance post-validation
  - adapte la surveillance et les criteres d'escalade au diagnostic valide
  - fichiers: [`llm.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\llm.py), [`postop-terrain-context-guidance.md`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\kb\postop-terrain-context-guidance.md)

- `PDF et exports`
  - assemble les donnees cliniques, la validation medicale, la conduite a tenir et les courbes
  - genere le PDF final
  - fichiers: [`clinical_report_service.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\services\reports\clinical_report_service.py), [`pdf_renderer.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\services\reports\pdf_renderer.py), [`export.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\export.py)

## Separation regles / ML / LLM

- `Regles`
  - seuils immediats
  - alertes critiques
  - fallback d'analyse si le LLM ne repond pas

- `ML`
  - apprend la criticite a partir de l'historique
  - produit un score longitudinal
  - ne choisit pas seul le diagnostic clinique final

- `LLM`
  - explique, synthétise et reformule
  - integre questionnaire, contexte patient et validation medicale
  - n'est pas fine-tune par le projet

## Validation medicale

Le projet separe:

- `pre-validation`: hypotheses libres par compatibilite clinique
- `post-validation`: diagnostic medical valide en tete, puis risques/points de surveillance a garder

Apres validation medicale:

- l'analyse clinique est rafraichie
- la conduite a tenir est recalculee
- le diagnostic valide sert d'ancre clinique
- le modele ML n'est pas reentraine automatiquement

## Notifications

Le projet supporte:

- notifications live dans l'application
- notifications navigateur
- Web Push via Service Worker + backend

Routes associees:

- `GET /api/push/config`
- `POST /api/push/subscriptions`
- `DELETE /api/push/subscriptions`

Limite importante:

- onglet ferme: possible selon le navigateur
- navigateur totalement ferme: comportement dependant du poste et du navigateur

## Organisation des fichiers

Arborescence utile:

```text
postop-monitoring/
|-- config/
|   |-- alert_rules.json
|   |-- cases_catalog.json
|   |-- patients_seed.json
|   |-- questionnaire_rules.json
|   `-- simulation_scenarios.json
|-- docs/
|   |-- api.md
|   |-- architecture.mmd
|   |-- case-generation.md
|   |-- clinical-references.md
|   |-- antecedents-context-catalog.md
|   |-- questionnaire-differentiel.md
|   `-- terrain-risk-weighting.md
|-- infra/
|   |-- mosquitto/
|   `-- postgres/
|-- kb/
|   |-- postop-home-monitoring-signs.md
|   |-- postop-terrain-context-guidance.md
|   `-- postop-terrain-context-sources.md
|-- runtime/
|   |-- .gitkeep
|   `-- ml/
|       |-- vitals.csv
|       |-- labeled_feedback.csv
|       `-- model.pkl
|-- scripts/
|   |-- seed_patients.py
|   |-- validate_rules.py
|   |-- setup_ollama_model.ps1
|   |-- backfill_alert_uncertainty.py
|   `-- outils annexes de generation / audit
|-- services/
|   |-- backend/
|   |   `-- app/
|   |       |-- alerting/
|   |       |-- llm/
|   |       |-- ml/
|   |       |-- mqtt/
|   |       |-- routers/
|   |       |-- services/
|   |       |-- storage/
|   |       |-- tests/
|   |       `-- ws/
|   |-- frontend/
|   |   `-- src/
|   |       |-- api/
|   |       |-- components/
|   |       |-- pages/
|   |       `-- types/
|   `-- simulator/
|       `-- app/
|-- docker-compose.yml
|-- start-demo.cmd
|-- start-demo.ps1
`-- start.sh
```

## Role des dossiers principaux

- [`config`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config): configuration clinique et scenarios
- [`docs`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs): documentation technique et clinique
- [`kb`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\kb): base de connaissances courte utilisee par le LLM
- [`runtime`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\runtime): donnees et artefacts locaux non versionnes
- [`services/backend`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend): logique centrale du projet
- [`services/frontend`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\frontend): dashboard web
- [`services/simulator`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\simulator): generation des constantes

## Fichiers backend importants

- [`main.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\main.py): assemblage de l'application
- [`routers/llm.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\llm.py): analyse clinique, questionnaire, conduite a tenir
- [`routers/ml.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\routers\ml.py): prediction et feedback ML
- [`mqtt/consumer.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\mqtt\consumer.py): ingestion temps reel
- [`alerting/engine.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\alerting\engine.py): regles d'alerte
- [`ml/criticity_service.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\ml\criticity_service.py): entrainement et prediction
- [`services/reports/clinical_report_service.py`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\backend\app\services\reports\clinical_report_service.py): construction du rapport clinique

## Fichiers frontend importants

- [`main.tsx`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\frontend\src\main.tsx): bootstrap de l'application
- [`pages/Patients.tsx`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\frontend\src\pages\Patients.tsx): liste des patients
- [`pages/PatientDetail.tsx`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\frontend\src\pages\PatientDetail.tsx): ecran principal patient
- [`api/http.ts`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\frontend\src\api\http.ts): appels REST
- [`api/ws.ts`](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\services\frontend\src\api\ws.ts): flux live

## Endpoints principaux

- `GET /health`
- `GET /api/patients`
- `GET /api/patients/{patient_id}/last-vitals`
- `GET /api/trends/{patient_id}?metric=all&hours=24`
- `GET /api/alerts?patient_id=PAT-003`
- `POST /api/alerts/{alert_id}/ack`
- `GET /api/export/{patient_id}/csv`
- `GET /api/export/{patient_id}/pdf`
- `GET /api/llm/{patient_id}/scenario-review`
- `GET /api/llm/{patient_id}/clinical-package`
- `GET /api/llm/{patient_id}/questionnaire`
- `POST /api/llm/{patient_id}/clinical-package`
- `POST /api/llm/{patient_id}/terrain-guidance`
- `GET /api/llm/prioritize/patients`
- `GET /api/ml/{patient_id}/predict`
- `POST /api/ml/{patient_id}/feedback`
- `POST /api/ml/train`
- `GET /api/notifications`
- `POST /api/notifications/{notification_id}/read`
- `WS /ws/live`

## Commandes utiles

```bash
make up
make start-demo
make down
make logs
make validate-rules
make seed
make refresh-alerts
```

## Demo conseillee

1. ouvrir la liste des patients
2. montrer `PAT-001` comme cas temoin stable
3. lancer un `Refresh demo`
4. ouvrir un patient pathologique
5. montrer le graphe `Depuis J0`
6. montrer alertes actives et historiques
7. afficher le pack clinique IA
8. remplir le questionnaire si propose
9. valider medicalement la pathologie si besoin
10. generer le PDF

## LLM local

Le projet utilise par defaut `qwen2.5:7b-instruct` via Ollama.

Fichiers utiles:

- [docs/llm-local.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\llm-local.md)
- [setup_ollama_model.ps1](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\scripts\setup_ollama_model.ps1)

Exemple d'activation:

```powershell
docker compose up -d ollama
.\scripts\setup_ollama_model.ps1 -StartOllama
docker compose up --build -d backend
```

Le backend retombe en `rule-based` si le LLM est indisponible ou trop lent.

## Limites actuelles

- le simulateur part de baselines encore proches d'un patient a l'autre
- le ML apprend surtout la criticite, pas un vrai diagnostic differentiel complet
- le LLM n'est pas fine-tune localement
- certaines notifications hors navigateur actif dependent du poste et du navigateur
- le mode demo reste prioritaire sur une exhaustivite clinique complete

## References utiles du projet

- [docs/architecture.mmd](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\architecture.mmd)
- [docs/case-generation.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\case-generation.md)
- [docs/clinical-references.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\clinical-references.md)
- [docs/antecedents-context-catalog.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\antecedents-context-catalog.md)
- [docs/questionnaire-differentiel.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\questionnaire-differentiel.md)
- [kb/postop-home-monitoring-signs.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\kb\postop-home-monitoring-signs.md)
- [config/alert_rules.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\alert_rules.json)
- [config/simulation_scenarios.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\simulation_scenarios.json)
- [config/patients_seed.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\patients_seed.json)
