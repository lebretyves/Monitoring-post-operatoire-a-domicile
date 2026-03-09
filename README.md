# Monitoring post-operatoire a domicile

Projet MBA1 Epitech du 4 mars 2026. L'objectif est simple: un projet simple qui marche, demo-friendly, avec une stack claire et des flux temps reel lisibles.

## Stack

- Simulator Python + `paho-mqtt`
- Mosquitto pour MQTT
- FastAPI pour REST + WebSocket
- InfluxDB pour les constantes vitales temps reel
- PostgreSQL pour les patients, alertes, notes et feedback ML
- React + Vite pour le dashboard
- IsolationForest pour le bonus anomalies
- Ollama local pour le bonus LLM, avec fallback `rule-based` visible
- Qwen 2.5 7B Instruct via Ollama pour les analyses IA

## Demarrage rapide

```bash
cp .env.example .env
docker compose up --build
```

## Lancement demo Windows

Le fichier de lancement principal est [start-demo.ps1](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\start-demo.ps1).

Il:

- cree `.env` si absent
- demarre Docker Desktop si le daemon n'est pas encore pret
- lance `docker compose up --build -d`
- attend le backend et le frontend
- ouvre automatiquement le dashboard web

Usage:

```powershell
.\start-demo.ps1
```

Ou en double-clic / terminal Windows:

```bat
start-demo.cmd
```

Ports par defaut:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`
- InfluxDB: `http://localhost:8086`
- PostgreSQL: `localhost:5432`
- Mosquitto MQTT: `localhost:1883`

## Services Docker

- `mosquitto`: broker MQTT avec topics structures
- `influxdb`: bucket `vitals` pour l'historique
- `postgres`: stockage relationnel
- `backend`: ingestion MQTT, regles, API, WebSocket
- `simulator`: 5 patients de demo en boucle
- `frontend`: dashboard React temps reel

## Demo conseillee

1. Ouvrir le dashboard Patients.
2. Montrer `PAT-001` comme patient temoin sain.
3. Lancer un `Refresh demo` pour tirer de nouveaux cas cliniques coherents.
4. Ouvrir un patient pathologique et montrer sa chirurgie, son jour post-op observe et sa complication plausible.
5. Afficher le graphe `Depuis J0` pour montrer la trajectoire clinique complete.
6. Basculer ensuite sur `24h`, `6h` ou `1h` pour zoomer la phase recente.
7. Afficher les alertes `INFO`, `WARNING`, `CRITICAL`.
8. Montrer les alertes actives puis les alertes historiques du cas.
9. Marquer une alerte comme vue depuis l'UI.
10. Montrer le resume patient et le pack clinique IA, avec etat `Ollama actif` ou `Fallback local actif`.
11. Sur la fiche patient, montrer le score ML longitudinal puis classer le cas et re-entrainer le modele.

## Mapping Must Have

- `M1` Simulateur multi-patients: 5 patients en continu (`PAT-001` a `PAT-005`) avec FC, SpO2, PA, MAP, T, FR. Le projet garde un temoin sain et plusieurs cas pathologiques de severite croissante, avec une baseline normale a `J0` puis des trajectoires postop differenciees.
- `M2` MQTT: Mosquitto + topics `patients/{id}/vitals` + QoS 1.
- `M3` Stockage temps reel: InfluxDB obligatoire pour `vitals`, PostgreSQL pour relationnel.
- `M4` Dashboard web: React temps reel via REST + WebSocket.
- `M5` Alertes: niveaux `INFO`, `WARNING`, `CRITICAL`, plus regle composite `SpO2 baisse + FC monte`.
- `M6` Docker Compose: `docker compose up` lance toute la stack.
- `M7` Documentation: README, Mermaid, topics MQTT, API, modele de donnees et script de demo.

## Extras inclus sans casser la demo

- ML anomalies: `IsolationForest` actif cote backend, secondaire dans l'UI.
- LLM summary: client Ollama actif avec fallback heuristique local visible si le modele ne repond pas.
- Historique `Depuis J0`, `24h`, `6h`, `1h` et tendances: endpoints et affichage frontend.
- Profils patients: antecedents, chirurgie, jour post-op dans `patients_seed.json`.
- Contexte patient et questionnaire differentiel: enrichissent l'analyse IA sans modifier le simulateur.
- Export CSV/PDF: endpoints reels dans l'API.
- Notifications: centre de notifications in-app + notifications navigateur sur alertes live.

## Endpoints principaux

- `GET /health`
- `GET /api/patients`
- `GET /api/patients/{patient_id}/last-vitals`
- `GET /api/trends/{patient_id}?metric=hr&hours=24`
- `GET /api/alerts?patient_id=PAT-003`
- `POST /api/alerts/{alert_id}/ack`
- `GET /api/export/{patient_id}/csv`
- `GET /api/export/{patient_id}/pdf`
- `GET /api/summaries/{patient_id}`
- `GET /api/llm/{patient_id}/scenario-review`
- `GET /api/llm/{patient_id}/clinical-package`
- `GET /api/llm/prioritize/patients`
- `GET /api/ml/{patient_id}/predict`
- `POST /api/ml/{patient_id}/feedback`
- `POST /api/ml/train`
- `WS /ws/live`

## Commandes utiles

```bash
make up
make start-demo
make down
make logs
make validate-rules
make seed
```

## Solution durable contre les blocages

- Blocage Docker Desktop non lance:
  utiliser `.\start-demo.ps1`, le script essaye de lancer Docker Desktop puis attend le daemon.
- Blocage `.env` manquant:
  le script copie automatiquement `.env.example` vers `.env`.
- Blocage service qui ne demarre pas:
  le script affiche `docker compose ps` et les derniers logs `backend/frontend/simulator`.
- Blocage ouverture page web:
  le script n'ouvre le navigateur qu'apres reponse HTTP du frontend.

## Structure utile

- [docker-compose.yml](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docker-compose.yml)
- [docs/architecture.mmd](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\architecture.mmd)
- [docs/case-generation.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\case-generation.md)
- [docs/clinical-references.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\clinical-references.md)
- [docs/questionnaire-differentiel.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\questionnaire-differentiel.md)
- [kb/postop-home-monitoring-signs.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\kb\postop-home-monitoring-signs.md)
- [config/alert_rules.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\alert_rules.json)
- [config/simulation_scenarios.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\simulation_scenarios.json)
- [config/patients_seed.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\patients_seed.json)

## Remarques de conception

- Les patients 2 a 5 reprennent ou derivent directement des scenarios du JSON source fourni.
- Le patient 1 reutilise la meme structure de simulation pour rester coherent mais reste stable pour la demo.
- Le refresh clinique tire des chirurgies compatibles avec chaque complication via une ponderation `forte/moyenne/faible = 70/20/10`.
- Chaque cas commence sur une baseline normale a `J0`, puis le simulateur reconstruit l'histoire complete jusqu'au temps clinique courant observe entre `J0` et `J3`.
- Les complications progressives se construisent sur plusieurs heures/jours cliniques simules; les complications brutales gardent un delai d'apparition aleatoire pendant la surveillance.
- Le graphe patient permet de voir l'histoire `Depuis J0`, puis de zoomer sur `24h`, `6h` ou `1h`.
- Le score ML et les analyses IA utilisent maintenant l'histoire `J0 -> maintenant`, pas seulement l'instantane recent.
- Les alertes historiques sont regenerees lors du backfill, puis se distinguent des alertes actives dans la fiche patient.
- Le contexte patient et le questionnaire differentiel n'influencent pas le simulateur; ils servent uniquement a enrichir l'analyse IA.
- Le calcul detaille des cas, jours post-op et combinaisons possibles est documente dans [case-generation.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\case-generation.md).
- Les extras ML et LLM sont facultatifs: ils n'empechent pas la demo si absents ou si le LLM retombe en fallback local.

## LLM local

Le support local Ollama utilise maintenant `qwen2.5:7b-instruct` comme modele par defaut:

- doc: [docs/llm-local.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\llm-local.md)
- script d'import/pull: [setup_ollama_model.ps1](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\scripts\setup_ollama_model.ps1)

Activation type:

```powershell
docker compose up -d ollama
.\scripts\setup_ollama_model.ps1 -StartOllama
docker compose up --build -d backend
```

Le service `ollama` fait partie du lancement standard. Si `ENABLE_LLM=true`, le backend pointe par defaut vers `qwen2.5:7b-instruct` avec un timeout de `90 s`.
Si le modele ne repond pas dans le delai imparti, l'UI affiche explicitement `Fallback local actif`.

## Bonnes pratiques retenues

- le moteur de regles reste prioritaire pour les seuils, la temporalite et les alertes critiques
- le LLM sert a expliquer, contextualiser et reformuler avec prudence
- les alertes affichent aussi une incertitude clinique: risque de faux positif, risque de faux negatif, remesure conseillee
- les donnees patients restent pseudonymisees
- le modele local est monte via volume externe et n'est pas versionne dans Git
- les references cliniques et IA/RGPD sont centralisees dans [clinical-references.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\clinical-references.md)
- une KB locale courte pour le LLM est disponible dans [kb/postop-home-monitoring-signs.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\kb\postop-home-monitoring-signs.md)
