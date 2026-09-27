<div align="center">

# 🔬 AI Research Agent

**Autonomous multi-agent intelligence platform for deep investigations, evidence verification, contradiction detection, and citation-backed synthesis.**

[![CI Pipeline](https://github.com/looayz/AI-research-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/looayz/AI-research-agent/actions)
[![Next.js 14](https://img.shields.io/badge/Frontend-Next.js%2014-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%200.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776ab?logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%2F%20SQLite-4169e1?logo=postgresql)](https://postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/Design-Monochrome%20Minimal-111111?logo=tailwindcss)](https://tailwindcss.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Architecture](#-architecture) •
[Key Features](#-key-features) •
[Quickstart](#-quickstart) •
[API Reference](#-api-endpoints) •
[Testing](#-testing) •
[Deployment](#-production--coolify)

</div>

---

## 🏛 Architecture

The AI Research Agent operates through a coordinated ensemble of specialized agents orchestrated via an asynchronous event-driven loop.

```
                          ┌──────────────┐
                          │     USER     │
                          └──────┬───────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Next.js 14 Minimal UI │
                     │   (Monochrome Theme)  │
                     └───────────┬───────────┘
                                 │ (REST / SSE)
                                 ▼
                     ┌───────────────────────┐
                     │   FastAPI Engine      │
                     └───────────┬───────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
       ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
       │   Planner   │    │ Researcher  │    │  Verifier   │
       │    Agent    │    │    Agent    │    │    Agent    │
       └─────────────┘    └─────────────┘    └─────────────┘
              │                  │                  │
              │         (Semantic Memory)           ▼
              │         ┌───────────────┐    ┌─────────────┐
              │         │ Vector Recall │    │     Gap     │
              │         └───────┬───────┘    │  Analyzer   │ (Deep Loop)
              │                 │            └─────────────┘
              │                 ▼                   │
              └─────────────────┴───────────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  Synthesizer  │
                         │     Agent     │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Cited Report  │
                         └───────────────┘
```

---

## 🚀 Key Features

### 1. 🔍 Autonomous Deconstruction & Planning
- **Planner Agent**: Breaks multi-faceted queries down into logically structured sub-inquiries.
- **Domain Specialization**: Adapts research strategies based on intent:
  - `Academic`: Targets peer-reviewed literature, arXiv preprints, meta-analyses, and `.edu` repositories.
  - `Technical`: Focuses on standard specifications, RFCs, official framework documentation, and GitHub repositories.
  - `Market`: Prioritizes industry statistics, SEC filings, competitive landscapes, and financial benchmarks.
  - `General`: Broad high-authority coverage across verified online publications.

### 2. 🛡️ Evidence Verification & Contradiction Engine
- **Verifier Agent**: Parses crawled content into verifiable, atomic `Claim` structures.
- **Support Status Evaluation**: Validates claims as `supported`, `partially_supported`, `contradicted`, or `insufficient_evidence`.
- **Contradiction Detection**: Cross-examines diverging claims between sources, isolates conflicting positions, and provides an impartial synthesis verdict.

### 3. 🔄 Deep Research & Recursive Gap Loop
- **Gap Analyzer Agent**: Quantifies evidentiary confidence across claims.
- **Autonomous Follow-Ups**: Dynamically issues targeted follow-up queries (`is_follow_up=True`) to resolve unanswered questions before concluding.
- **Three Depth Presets**:
  - `Quick`: Fast single-pass reconnaissance.
  - `Standard`: Multi-source cross-verification with claim extraction.
  - `Deep Loop`: Recursive evidence-gap analysis with secondary retrieval iterations.

### 4. 🧠 Semantic Research Memory
- Generates 128-dimensional normalized vector embeddings for all ingested documents.
- **Cross-Session Recall**: Past sources relevant to new investigations are automatically retrieved and injected into the current context.
- **Vector Search Endpoint**: `POST /api/memory/search` with threshold filtering and cosine similarity ranking.

### 5. ⚡ Real-Time Telemetry & Modern UI
- **Server-Sent Events (SSE)**: Streams agent state changes, search queries, and claim verifications live to `/api/research/{id}/events`.
- **Minimalist Aesthetic**: Off-white background (`#f7f7f5`) paired with clean black typography and high-contrast accents.
- **Human-in-the-Loop Source Control**: Exclude untrusted or hallucinated sources with one click to trigger report re-synthesis.
- **One-Click Markdown Export**: Download complete reports formatted with traceable citations.

---

## 🛠 Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide Icons |
| **Backend** | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0 (Async), Alembic |
| **Storage & Caching** | PostgreSQL 16 / SQLite (aiosqlite), Redis 7 (pub/sub & telemetry) |
| **AI Layer** | Modular Provider Abstraction (`MockLLM`, `OpenAI`, `Gemini`) |
| **Search Layer** | Pluggable Providers (`MockSearch`, `DuckDuckGo`, `Tavily`) |
| **Extraction & Security** | Anti-SSRF URL Validation, Private IP Filtering, BeautifulSoup |
| **DevOps & CI** | Multi-stage Docker, GitHub Actions, Coolify Deployments |

---

## ⚡ Quickstart

### Option A: Run with Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/looayz/AI-research-agent.git
cd AI-research-agent

# Set up environment variables
cp .env.example .env

# Build and start services
docker compose up --build
```

- **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Option B: Local Development Setup

#### 1. Backend (FastAPI)

```bash
# Create virtual environment
python -m venv .venv

# Activate environment
.\.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux / macOS

# Install dependencies
pip install -r apps/api/requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend (Next.js 14)

```bash
cd apps/web

# Install packages
npm install

# Start development server
npm run dev
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health status, database check, and provider configuration |
| `POST` | `/api/research` | Create and execute an autonomous investigation session |
| `GET` | `/api/research` | Retrieve all past research investigations |
| `GET` | `/api/research/{id}` | Inspect full details of a session (queries, sources, claims, contradictions, report) |
| `GET` | `/api/research/{id}/events` | Real-time SSE event stream for live telemetry |
| `POST` | `/api/research/{id}/rerun` | Re-run an existing research query |
| `DELETE` | `/api/research/{id}` | Delete a past investigation from database |
| `POST` | `/api/research/{id}/sources/{s_id}/exclude` | Exclude a specific source from citation |
| `POST` | `/api/memory/search` | Vector similarity search across all historical sources |

### Example Research Request:

```bash
curl -X POST "http://localhost:8000/api/research" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Impact of quantum computing on modern cryptography",
    "depth": "deep",
    "domain": "technical"
  }'
```

---

## 🧪 Testing

Execute backend test suites covering agents, claim verification, gap analyzer, and semantic vector embeddings:

```bash
# Set PYTHONPATH and run Pytest
$env:PYTHONPATH="apps/api"
.\.venv\Scripts\pytest apps/api/tests -v
```

Execute frontend build verification:

```bash
cd apps/web
npm run build
```

---

## 🚢 Production & Coolify

The repository includes pre-configured, production-hardened Dockerfiles and CI workflows:

- **Multi-Stage API Dockerfile**: [apps/api/Dockerfile](file:///d:/Projects/AI%20reasearch%20agent/apps/api/Dockerfile) (slim Debian, non-root user `appuser`, built-in healthcheck).
- **Multi-Stage Web Dockerfile**: [apps/web/Dockerfile](file:///d:/Projects/AI%20reasearch%20agent/apps/web/Dockerfile) (Node.js 18 alpine, standalone Next.js server).
- **Coolify Deployment Guide**: Detailed step-by-step instructions available in [docs/COOLIFY_DEPLOYMENT.md](file:///d:/Projects/AI%20reasearch%20agent/docs/COOLIFY_DEPLOYMENT.md).
- **GitHub Actions CI**: Automated test & build validation defined in [.github/workflows/ci.yml](file:///d:/Projects/AI%20reasearch%20agent/.github/workflows/ci.yml).

---

## 📄 License

Distributed under the [MIT License](file:///d:/Projects/AI%20reasearch%20agent/LICENSE). See `LICENSE` for more information.
