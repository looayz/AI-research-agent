# Deployment guide (Coolify or any Docker host)

The stack is defined in `docker-compose.yml`: `web` (Next.js, port 3000) → `api` (FastAPI, port 8000) → `postgres` + `redis`.
Only **web** needs to be public: it proxies `/api/*` (SSE included) to the API over the internal network.

## 1. Coolify

1. Create a new resource → **Docker Compose** → connect this repository (branch `main`), compose file `docker-compose.yml`.
2. Assign your domain to the **web** service, port `3000`. Do not give the api, postgres or redis services a domain.
3. Set the environment variables (Coolify injects them into the compose file):

   | Variable | Example |
   |---|---|
   | `POSTGRES_PASSWORD` | a long random string (required: change the default) |
   | `LLM_PROVIDER` / `LLM_MODEL` | `openai` / `gpt-4o-mini`, `anthropic` / `claude-opus-5-5`, `gemini`… |
   | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`… | the key of the chosen provider |
   | `SEARCH_PROVIDER` | `tavily`, `searxng`, `wikipedia,duckduckgo`… |
   | `TAVILY_API_KEY` / `SEARXNG_BASE_URL` | if needed |
   | `MAX_RUNTIME_SECONDS`, `MAX_SOURCES` | optional limits |

   The api service reads the same variables as `.env.example`.
4. **Protect the app**: there is no built-in authentication and every research consumes API credits. Enable basic auth on the web domain (Coolify → service → *Basic Auth*, or a Traefik `basicauth` middleware), or put it behind Cloudflare Access or a VPN.
5. Deploy. The health checks wait for PostgreSQL and Redis, then the API, then the web app.

## 2. Plain Docker host

```bash
cp .env.example .env    # set POSTGRES_PASSWORD, providers and keys
docker compose up --build -d
docker compose ps       # every service should be "healthy"
curl http://localhost:3000/api/health
```

By default the API port is bound to `127.0.0.1:8000` on the host (`API_PORT`), so only the web app (`WEB_PORT`, default 3000) is reachable from outside. Put a TLS reverse proxy with authentication in front of it.

Updates: `git pull && docker compose up --build -d`. The database schema is upgraded automatically at startup (additive changes only).

## 3. Hardening checklist

- [x] Non-root containers (uid 1001), health checks on every service.
- [x] PostgreSQL and Redis are not published on the host; Redis runs as a bounded, non-persistent cache.
- [x] SSRF protection for fetched pages (public addresses only, checked at connect time and on each redirect).
- [x] Security headers on the web app (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`).
- [ ] Authentication in front of the web app (your reverse proxy).
- [ ] Strong `POSTGRES_PASSWORD`.
- [ ] Backups of the `postgres_data` volume.
