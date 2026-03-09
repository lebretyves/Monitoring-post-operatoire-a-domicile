# LLM local Qwen 2.5 7B Instruct

Le projet supporte un LLM local via API Ollama.

Objectif actuel:

- resume automatique
- revue de scenario clinique
- confirmation ou infirmation prudente du scenario courant

Le LLM ne remplace pas le moteur d'alertes. Il agit comme une aide a l'orientation clinique.

## Modele retenu

- bibliotheque Ollama: `qwen2.5:7b-instruct`
- usage vise: sorties JSON structurees, synthese clinique courte, hypotheses et questions differentielles
- activation simple par `ollama pull`, sans fichier `.gguf` ni Modelfile custom

## Configuration

Variables a verifier dans [.env.example](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\.env.example):

- `ENABLE_LLM=false`
- `OLLAMA_PORT=11434`
- `OLLAMA_MODEL=qwen2.5:7b-instruct`
- `OLLAMA_TIMEOUT_SECONDS=90`

## Arborescence

- script de pull/import: [setup_ollama_model.ps1](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\scripts\setup_ollama_model.ps1)

## Import dans Ollama

1. Demarrer Ollama:

```powershell
docker compose up -d ollama
```

2. Telecharger le modele:

```powershell
.\scripts\setup_ollama_model.ps1 -StartOllama
```

3. Activer le LLM dans `.env`:

```env
ENABLE_LLM=true
OLLAMA_MODEL=qwen2.5:7b-instruct
```

4. Rebuild le backend:

```powershell
docker compose up --build -d backend
```

## Endpoints utiles

- `GET /api/summaries/{patient_id}`
- `GET /api/llm/{patient_id}/scenario-review`

## Bonnes pratiques retenues

- le LLM reste une aide a l'orientation clinique, jamais un moteur de diagnostic autonome
- les seuils et alertes critiques restent portes par le moteur de regles, pas par le modele
- le LLM explique et reformule, mais n'invente ni seuil, ni protocole, ni prescription
- les donnees directes identifiantes ne doivent pas etre envoyees au modele
- l'identifiant patient reste pseudonymise
- en absence de source RAG, le systeme doit expliciter `source non disponible`
- en cas de signes de gravite immediate, l'escalade de securite prime sur toute interpretation longue
- le fallback `rule-based` reste actif si Ollama ou le modele ne repond pas
- pour limiter les faux positifs, les alertes sont interpretees avec persistance, tendance et contexte
- pour limiter les faux negatifs, les cas restent a reevaluer apres remesure selon la gravite

References et bonnes pratiques officielles:

- voir [clinical-references.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\clinical-references.md), section `IA medicale, prudence clinique et confidentialite`
- voir [clinical-references.md](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\docs\clinical-references.md), section `Alerte precoce, escalation et reduction des faux positifs`

## Reponse attendue du scenario review

Le backend attend une sortie structuree avec:

- `scenario_confirmed`
- `confidence`
- `primary_hypothesis`
- `alternatives`
- `supporting_signals`
- `contradicting_signals`
- `clinical_priority`
- `recommended_action`

## Comportement si le modele n'est pas pret

- si Ollama est indisponible
- si le modele n'est pas encore importe
- si la reponse est invalide

alors l'API renvoie une analyse `rule-based` au lieu d'une erreur bloquante.

## Limite actuelle

- le service `ollama` demarre avec la stack standard
- sur une machine modeste, `qwen2.5:7b-instruct` peut encore rester lent sur les routes d'analyse les plus lourdes
- dans ce cas, l'API et l'UI affichent explicitement que la reponse provient du `Fallback local actif`
