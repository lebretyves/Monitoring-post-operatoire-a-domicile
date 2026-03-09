# KB locale

Ce dossier contient une base de connaissances locale, statique et courte, exploitable
par le LLM sans moteur RAG complexe.

Objectif:

- fournir des rappels cliniques simples et tracables
- aider le LLM a raisonner sur des donnees de domicile
- eviter de lui donner le scenario simule interne

Perimetre:

- signes observables a domicile
- elements aidant au diagnostic differentiel
- formulation prudente compatible avec un outil d'aide a l'orientation

Limites:

- ce n'est pas un moteur de recherche semantique
- ce n'est pas une base medicale exhaustive
- les extraits doivent rester courts pour ne pas ralentir Ollama

## Fichiers

- `postop-home-monitoring-signs.md`
  - KB runtime actuelle, courte, deja relue par le backend
- `postop-terrain-context-guidance.md`
  - recommandations synthetiques par terrain patient et contexte peri-op
- `postop-terrain-context-sources.md`
  - index des sources par categorie, avec `ce que la source soutient`

## Regle pratique

- les fichiers `guidance` et `sources` sont prepares pour un futur usage LLM par categorie
- ils ne sont pas encore injectes automatiquement dans le prompt runtime actuel
- pour le runtime actuel, garder `postop-home-monitoring-signs.md` courte et stable
