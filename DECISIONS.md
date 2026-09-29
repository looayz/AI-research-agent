# Architectural Decision Records (ADR)

## ADR-001: Modular monolith backend with FastAPI

- **Status**: Accepted
- **Context**: Multi-agent workflows, persistence, background execution and many outbound calls.
- **Decision**: One Python FastAPI service (`apps/api`) with agents, providers and services as modules.
- **Consequences**: Direct access to the Python AI ecosystem, no inter-service overhead, a single container to deploy.

## ADR-002: Provider abstractions for LLM and search

- **Status**: Accepted (implemented in v0.3)
- **Decision**: `LLMProvider` and `SearchProvider` interfaces with offline mock implementations. Providers are chosen by `LLM_PROVIDER` / `SEARCH_PROVIDER`; `MOCK_MODE=true` forces the mocks.
- **Implementations**: OpenAI-compatible (OpenAI, Groq, OpenRouter, Ollama, any `LLM_BASE_URL`), Gemini (REST), Anthropic (official SDK); Tavily, SearXNG, DuckDuckGo, Wikipedia, arXiv, composable with commas.
- **Consequences**: The whole test suite runs without keys or network. Optional parameters that some OpenAI-compatible APIs reject are dropped automatically on a 400.

## ADR-003: SSE backed by the database, in-process wake-ups

- **Status**: Accepted (revised in v0.3; the first version described a Redis pub/sub that did not exist)
- **Decision**: Events are persisted with a per-research sequence number. The SSE endpoint replays them and polls for new ones; an in-process event bus wakes the stream immediately when the event comes from the same process. `Last-Event-ID` / `?after=` resume a broken stream.
- **Consequences**: Correct across several workers without extra infrastructure; the terminal status is committed with the final event so streams always end.

## ADR-004: SQLAlchemy 2.0 async, create_all + additive schema sync

- **Status**: Accepted (revised in v0.3; Alembic was announced but never configured)
- **Decision**: Tables are created at startup; columns added later are appended with `ALTER TABLE ... ADD COLUMN` (nullable or defaulted) and back-filled once. Datetimes are stored as naive UTC through a `TypeDecorator` and returned timezone-aware.
- **Consequences**: Existing SQLite/PostgreSQL databases upgrade in place. Move to Alembic before any destructive schema change.

## ADR-005: Treat fetched URLs as hostile (SSRF)

- **Status**: Accepted
- **Decision**: Only http(s) without credentials; every resolved address must be globally routable; the check is repeated inside the connection (custom httpcore network backend) against DNS rebinding; redirects are followed manually and re-validated; size and content types are capped. With an outbound proxy, the pre-request validation of every hop applies.
- **Consequences**: `FETCH_ALLOW_PRIVATE_NETWORKS=true` exists for trusted local setups only.

## ADR-006: Never fabricate evidence

- **Status**: Accepted
- **Decision**: No synthetic fallback content outside the explicit demo providers. An unreachable page falls back to the real search snippet (flagged) or is skipped; an unusable model answer gets one repair attempt, then a visible warning and an empty result.
- **Consequences**: Reports can be thinner when things fail, but every citation points to something that was actually retrieved.

## ADR-007: Same-origin API proxy in the web app

- **Status**: Accepted
- **Decision**: The browser calls `/api/*` on the web origin; a Next.js route handler forwards to `API_INTERNAL_URL` at request time and streams bodies (SSE included). `NEXT_PUBLIC_API_URL` can still point the browser at the API directly.
- **Consequences**: One public port, no CORS, one image deployable anywhere (the target is runtime configuration).

## ADR-008: Lexical embeddings for the memory

- **Status**: Accepted, to revisit
- **Decision**: Local signed feature hashing of unigrams and bigrams (256 dimensions, stop words removed, plural folding), cosine similarity in Python, URL de-duplication.
- **Consequences**: Zero dependencies and no API calls, but no synonym matching and a full scan per query. Next step: an embedding provider plus pgvector.
