# AI Research Agent

A multi-agent AI research platform that autonomously investigates complex questions, collects evidence from multiple sources, cross-checks claims, detects contradictions, and generates transparent research reports with verified citations.

---

## 🏛 Architecture Overview

```
                         ┌──────────────┐
                         │     USER     │
                         └──────┬───────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   NEXT.JS UI    │
                       └────────┬────────┘
                                │ (REST / SSE)
                                ▼
                       ┌─────────────────┐
                       │   FASTAPI API   │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ RESEARCH ENGINE │
                       └────────┬────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        ┌──────────┐      ┌──────────┐      ┌──────────┐
        │ Planner  │      │Researcher│      │ Verifier │
        │  Agent   │      │  Agent   │      │  Agent   │
        └──────────┘      └──────────┘      └──────────┘
              │                 │                 │
              │          (Semantic Memory)        ▼
              │          ┌──────────────┐   ┌──────────┐
              │          │Vector Recall │   │   Gap    │
              │          └──────┬───────┘   │ Analyzer │ (Deep Research Loop)
              │                 │           └──────────┘
              │                 ▼                 │
              └─────────────────┴─────────────────┘
                                │
                                ▼
                         ┌─────────────┐
                         │ Synthesizer │
                         │    Agent    │
                         └──────┬──────┘
                                │
                                ▼
                         ┌─────────────┐
                         │ Cited Report│
                         └─────────────┘
```

## ⚡ Tech Stack

- **Frontend**: Next.js 14+ (App Router), React, TypeScript, Tailwind CSS, Lucide Icons, EventSource (SSE).
- **Backend**: FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0 (asyncpg), Alembic.
- **Database**: PostgreSQL 16 (with asyncpg pooling and vector embedding persistence).
- **Cache & Telemetry**: Redis 7.
- **AI Providers**: Abstracted multi-provider layer (`MockLLMProvider`, `OpenAIProvider`, `GeminiProvider`).
- **Search Providers**: Abstracted web search layer (`MockSearchProvider`, `DuckDuckGo`, `Tavily`).
- **Security & Extraction**: Anti-SSRF URL filtering, HTML noise stripping via BeautifulSoup.
- **Production & CI**: Multi-stage Docker builds, GitHub Actions (`.github/workflows/ci.yml`), Coolify-compatible.

---

## 🚀 Key Features

1. **Production Packaging & Coolify Deployment**:
   - Hardened multi-stage Docker builds with non-root security principles and automated healthcheck directives.
   - GitHub Actions CI matrix running automated tests and static page compilation on every commit.
   - Comprehensive deployment documentation in [`docs/COOLIFY_DEPLOYMENT.md`](file:///d:/Projects/AI%20reasearch%20agent/docs/COOLIFY_DEPLOYMENT.md).
2. **Semantic Research Memory & Cross-Investigation Recall**:
   - Computes normalized vector embeddings for each retrieved document.
   - Automatically queries and re-injects relevant past sources into new research sessions (`POST /api/memory/search`).
   - Dedicated Semantic Memory Explorer in the frontend for freeform vector exploration.
3. **Domain Specialization Profiles**:
   - **Academic**: Prioritizes peer-reviewed publications, arXiv preprints, meta-analyses, and educational institutions (`.edu`).
   - **Technical**: Targets official language specifications, RFCs, GitHub repositories, and software architecture docs.
   - **Market**: Investigates industry metrics, financial filings, competitor benchmarks, and growth figures.
   - **General**: Broad authoritative web coverage.
4. **Autonomous Deconstruction (Planner Agent)**:
   - Decomposes complex user questions into sub-questions and focused search queries tailored to the selected domain.
5. **Multi-Source Scraping & Domain Classification (Researcher Agent)**:
   - Queries web providers, crawls target URLs, filters out HTML boilerplate, extracts content safely, and scores domain relevance.
6. **Evidence Verification & Contradiction Engine (Verifier Agent)**:
   - Extracts factual assertions into structured `Claim` objects.
   - Evaluates statuses: `supported`, `partially_supported`, `contradicted`, `insufficient_evidence`.
   - Identifies opposing claims and analyzes discrepancies (methodology, target audience, timeframe).
7. **Deep Research Loop & Evidence Gap Analysis (Gap Analyzer Agent)**:
   - Analyzes claims with low confidence or partial evidence.
   - Formulates targeted follow-up queries (`is_follow_up=True`) and conducts second-pass crawling before synthesis.
8. **Transparent Synthesis with Traceable Citations (Synthesizer Agent)**:
   - Generates comprehensive markdown research reports with numbered citations `[1]`, `[2]` linking strictly to inspected sources.
   - Dedicated interactive Citation Registry block with source type and direct hyperlinks.
9. **Real-Time Streaming Timeline (SSE)**:
   - Streams live agent thoughts and stage transitions directly to the browser.
10. **Research History & Human Control**:
   - Save and browse previous researches with domain and depth badges.
   - Re-run any past research with a single click.
   - Delete past inquiries.
   - Exclude untrusted sources before final synthesis.
   - Direct Export to Markdown (`.md`).

---

## 🛠 Quick Start

### 1. Environment Configuration

```bash
cp .env.example .env
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

- **Frontend Console**: http://localhost:3000
- **FastAPI Interactive Docs**: http://localhost:8000/docs
- **Health Check Endpoint**: http://localhost:8000/health

### 3. Run Locally (Development)

#### Backend:
```bash
# Activate virtual environment
.\.venv\Scripts\activate  # Windows
source .venv/bin/activate # Linux / macOS

# Install dependencies
pip install -r apps/api/requirements.txt

# Launch FastAPI server
uvicorn app.main:app --reload --port 8000
```

#### Frontend:
```bash
cd apps/web
npm install
npm run dev
```

---

## 🧪 Testing

Run all unit and integration tests with Pytest:

```bash
$env:PYTHONPATH="apps/api"
.\.venv\Scripts\pytest apps/api/tests
```

---

## 🗺 Features Roadmap & Status

- [x] **Phase 0 — Foundation**: Repository scaffolding, Docker Compose, DB/Redis, Health checks, Docs.
- [x] **Phase 1 — Basic Research**: Planner, Researcher, Content Extractor with SSRF protections, Synthesizer with citations.
- [x] **Phase 2 — Verification & Contradictions**: Claim extraction, Contradiction engine, multi-source cross-checking.
- [x] **Phase 3 — Real-Time Events & Streaming UI**: SSE live stream, pipeline stepper, human-in-the-loop source exclusion.
- [x] **Phase 4 — Research History & Persistence**: Research history management, one-click rerun, delete, markdown export.
- [x] **Phase 5 — Deep Research**: Recursive evidence gap analysis, automated follow-up queries, 3 depth modes (`Quick`, `Standard`, `Deep`).
- [x] **Phase 6 — Domain Specialization**: Academic, Technical, Market, and General specialized researcher modes with Citation Registry.
- [x] **Phase 7 — Semantic Research Memory**: Cross-investigation document vector recall, similarity search endpoint (`/api/memory/search`) and interactive UI explorer.
- [x] **Phase 8 — Production Packaging**: Multi-stage slim Docker builds, Coolify-ready configuration, GitHub Actions CI workflow.
