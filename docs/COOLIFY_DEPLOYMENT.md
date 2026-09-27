# Coolify & Production Deployment Guide

## 1. Coolify Deployment

AI Research Agent is designed for single-click deployment using Docker Compose on Coolify or any VPS.

### Configuration Steps on Coolify:
1. In Coolify, create a new **Service** and select **Docker Compose**.
2. Connect your Git repository (`main` branch).
3. Set the following environment variables:
   - `APP_ENV=production`
   - `MOCK_MODE=false` (or `true` if you wish to run deterministic demo tests without external keys)
   - `POSTGRES_USER=postgres`
   - `POSTGRES_PASSWORD=<strong_random_password>`
   - `POSTGRES_DB=ai_research_agent`
   - `OPENAI_API_KEY=<your_key_here>` (or `GEMINI_API_KEY`)
   - `SEARCH_PROVIDER=duckduckgo` (or `tavily`)
   - `TAVILY_API_KEY=<your_tavily_key>`
4. Deploy the stack. Coolify automatically attaches Traefik reverse proxy routing:
   - Web frontend exposed on port `3000`.
   - API backend exposed on port `8000`.

---

## 2. Docker Compose Commands

### Production start:
```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### Check service health:
```bash
docker compose ps
curl http://localhost:8000/health
```

---

## 3. Production Hardening Checklist

- [x] Multi-stage slim Docker builds (non-root runner user on web & minimal Python runner).
- [x] SSRF guards actively blocking internal subnets and private loopbacks in `ContentExtractor`.
- [x] Connection pooling and pre-ping on SQLAlchemy engine.
- [x] Continuous healthchecks configured on Postgres, Redis, and FastAPI containers.
- [x] Automated GitHub Actions CI workflow running unit tests on every pull request.
