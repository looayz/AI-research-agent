# Project Status

## Current version: 0.3.0 (review and hardening)

The first version (phases 0 to 8) was reported as complete, but only the demo path on SQLite actually worked. Version 0.3 fixes that; see [docs/REVIEW.md](docs/REVIEW.md) for the full review.

### Done

- [x] **Foundation**: FastAPI + Next.js monorepo, SQLite by default, PostgreSQL + Redis with Docker Compose.
- [x] **Research pipeline**: planner, researcher (concurrent search and fetch, scoring), verifier, gap analyzer, synthesizer.
- [x] **Depth modes** with an actual loop: quick (0 rounds), standard (1), deep (up to 3, re-verified each round).
- [x] **Real providers**: OpenAI-compatible, Gemini, Anthropic; Tavily, SearXNG, DuckDuckGo, Wikipedia, arXiv.
- [x] **Safety**: SSRF-safe fetching, no fabricated fallbacks, bounded inputs, non-root containers.
- [x] **Live UI**: SSE with resume, pipeline view, activity timeline, progressive results.
- [x] **Human in the loop**: exclude/include sources, regenerate the report, cancel, rerun.
- [x] **History and memory**: search, filters, pagination; memory recall with URL de-duplication.
- [x] **Exports**: Markdown, JSON, print/PDF.
- [x] **Packaging**: working Docker images, compose (prod + dev), CI (SQLite + PostgreSQL, web, Docker smoke test).
- [x] **Tests**: 103 hermetic backend tests.

### Next

- [ ] Authentication and rate limiting (until then: deploy behind an authenticating proxy).
- [ ] Embedding provider + pgvector for the memory.
- [ ] External task queue for multi-worker deployments.
- [ ] Alembic migrations.
- [ ] PDF extraction, JavaScript-rendered pages.
- [ ] Evaluation set to compare models, prompts and depths.
- [ ] Token-by-token report streaming.
