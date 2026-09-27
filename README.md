<div align="center">

# AI Research Agent

**Autonomous multi-agent intelligence platform for deep investigations, evidence verification, and citation-backed synthesis.**

[English](#-english) • [Français](#-version-française)

[![CI Pipeline](https://github.com/looayz/AI-research-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/looayz/AI-research-agent/actions)
[![Next.js 14](https://img.shields.io/badge/Next.js-14.1-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776ab?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## 🇬🇧 English

An autonomous research engine that coordinates specialized AI agents to crawl sources, verify factual claims, isolate contradictions, and synthesize transparent, cited research reports.

### Quick Start (One Command)

#### Windows
Double-click `start.bat` or run:
```cmd
.\start.bat
```

#### macOS / Linux
```bash
chmod +x start.sh
./start.sh
```

#### Docker Compose
```bash
cp .env.example .env
docker compose up --build
```

- **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Healthcheck**: [http://localhost:8000/health](http://localhost:8000/health)

---

### How It Works

```
Question ──► [Planner] ──► [Researcher] ──► [Verifier] ──► [Gap Analyzer] ──► [Synthesizer] ──► Report
                               ▲                                 │ (Deep Loop)
                               └────── (Follow-up Queries) ──────┘
```

1. **Planner Agent**: Decomposes user queries into domain-targeted research questions (`Academic`, `Technical`, `Market`, `General`).
2. **Researcher Agent**: Searches the web, crawls content with anti-SSRF protections, extracts text, and recalls past findings via **Semantic Memory** (128-dim normalized vector embeddings).
3. **Verifier Agent**: Extracts atomic claims and classifies evidence (`supported`, `partially_supported`, `contradicted`, `insufficient_evidence`).
4. **Gap Analyzer Agent**: Identifies missing evidence and triggers automated follow-up queries (`is_follow_up=True`).
5. **Synthesizer Agent**: Generates a clean Markdown report with traceable, numbered citations `[1]`, `[2]` linked to real inspected sources.

---

### Repository Structure

```
.
├── apps/
│   ├── api/             # FastAPI backend (agents, database, vector memory)
│   └── web/             # Next.js 14 frontend (Tailwind CSS, monochrome theme)
├── docs/                # Deployment guides (Coolify, Docker)
├── docker-compose.yml   # Multi-container orchestration (API, Web, Redis, Postgres)
├── start.bat            # Windows 1-click runner
├── start.sh             # Linux / macOS 1-click runner
└── package.json         # Monorepo scripts
```

---

### API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status and configured providers |
| `POST` | `/api/research` | Create and execute a research session |
| `GET` | `/api/research` | List past investigations |
| `GET` | `/api/research/{id}` | Get full details (claims, contradictions, report) |
| `GET` | `/api/research/{id}/events` | Real-time SSE event stream for live telemetry |
| `POST` | `/api/research/{id}/rerun` | Re-run an investigation |
| `DELETE` | `/api/research/{id}` | Delete an investigation |
| `POST` | `/api/research/{id}/sources/{s_id}/exclude` | Exclude a source from citations |
| `POST` | `/api/memory/search` | Search cross-investigation semantic vector memory |

---

### Testing

```bash
# Backend unit & integration tests
$env:PYTHONPATH="apps/api"; .\.venv\Scripts\pytest apps/api/tests

# Frontend build check
cd apps/web && npm run build
```

---

## 🇫🇷 Version Française

Plateforme de recherche autonome multi-agents capable d'analyser des sujets complexes, de vérifier les faits, d'identifier les contradictions entre sources et de synthétiser des rapports documentés avec citations vérifiables.

### Lancement Rapide (En une seule commande)

#### Windows
Double-cliquez sur `start.bat` ou lancez :
```cmd
.\start.bat
```

#### macOS / Linux
```bash
chmod +x start.sh
./start.sh
```

#### Avec Docker
```bash
cp .env.example .env
docker compose up --build
```

- **Interface Web** : [http://localhost:3000](http://localhost:3000)
- **Documentation API** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **Vérification de santé** : [http://localhost:8000/health](http://localhost:8000/health)

---

### Fonctionnement du Pipeline

```
Question ──► [Planification] ──► [Recherche] ──► [Vérification] ──► [Analyse Lacunes] ──► [Synthèse] ──► Rapport
                                      ▲                                    │ (Boucle Deep)
                                      └────── (Requêtes de suivi) ─────────┘
```

1. **Agent Planificateur** : Décompose les questions selon le profil sélectionné (`Académique`, `Technique`, `Marché`, `Général`).
2. **Agent Chercheur** : Effectue la collecte web avec protection anti-SSRF, nettoie le HTML et réutilise les connaissances passées via la **Mémoire Sémantique** (vecteurs normalisés 128 dimensions).
3. **Agent Vérificateur** : Extrait les affirmations clés et leur statut (`supported`, `partially_supported`, `contradicted`, `insufficient_evidence`).
4. **Analyseur de Lacunes (Deep Loop)** : Détecte les zones d'incertitude et relance des recherches ciblées en arrière-plan.
5. **Agent Synthétiseur** : Produit un rapport structuré au format Markdown avec citations numérotées `[1]`, `[2]` liées aux sources vérifiées.

---

### Fonctionnalités Clés

- **Interface Moderne Monochrome** : Design minimaliste noir et blanc cassé (`#f7f7f5`), contraste élevé, typographie nette.
- **Télémétrie Temps Réel** : Streaming SSE direct des réflexions des agents vers le navigateur.
- **Contrôle Humain** : Exclusion de sources indésirables en un clic avec recalcul du rapport.
- **Historique & Rerun** : Sauvegarde locale de toutes les recherches et relance instantanée.
- **Export Markdown** : Téléchargement direct des rapports complets en un clic.
- **Déploiement Prêt à l'Emploi** : Dockerfiles légers multi-étapes et guide de déploiement Coolify inclus dans `docs/COOLIFY_DEPLOYMENT.md`.

---

## 📄 License

Distribué sous licence MIT. Voir `LICENSE` pour plus de détails.
