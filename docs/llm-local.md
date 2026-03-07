# LLM local Meditron 8B

Le projet supporte un LLM local via API Ollama.

Objectif actuel:

- resume automatique
- revue de scenario clinique
- confirmation ou infirmation prudente du scenario courant

Le LLM ne remplace pas le moteur d'alertes. Il agit comme une aide a l'orientation clinique.

## Modele retenu

- source Hugging Face: `QuantFactory/Meditron3-8B-GGUF`
- fichier local attendu: `Meditron3-8B.Q4_0.gguf`
- format: `.gguf`
- dossier local conseille: `C:\models`

## Configuration

Variables a verifier dans [.env.example](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\.env.example):

- `ENABLE_LLM=false`
- `OLLAMA_PORT=11434`
- `OLLAMA_MODEL=meditron-8b-local`
- `OLLAMA_GGUF_HOST_DIR=C:/models`
- `OLLAMA_GGUF_FILENAME=Meditron3-8B.Q4_0.gguf`

## Arborescence

- template Ollama: [Modelfile.meditron.template](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\infra\ollama\Modelfile.meditron.template)
- script de download: [download_meditron_gguf.ps1](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\scripts\download_meditron_gguf.ps1)
- script d'import: [setup_ollama_model.ps1](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\scripts\setup_ollama_model.ps1)

## Telechargement

Installer l'outil Hugging Face:

```powershell
py -m pip install -U huggingface_hub
```

Telecharger le GGUF:

```powershell
.\scripts\download_meditron_gguf.ps1
```

Equivalent manuel:

```powershell
huggingface-cli download QuantFactory/Meditron3-8B-GGUF `
  Meditron3-8B.Q4_0.gguf `
  --local-dir C:\models `
  --local-dir-use-symlinks False
```

## Import dans Ollama

1. Demarrer Ollama:

```powershell
docker compose --profile llm up -d ollama
```

2. Importer le modele:

```powershell
.\scripts\setup_ollama_model.ps1 -StartOllama
```

3. Activer le LLM dans `.env`:

```env
ENABLE_LLM=true
OLLAMA_MODEL=meditron-8b-local
OLLAMA_GGUF_HOST_DIR=C:/models
OLLAMA_GGUF_FILENAME=Meditron3-8B.Q4_0.gguf
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
