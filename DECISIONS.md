# Architectural Decision Records (ADR)

## ADR-001: Modular Monolith Backend with FastAPI

- **Status**: Accepted
- **Context**: The AI Research Agent requires an extensible orchestration layer for multi-agent workflows, DB persistence, background execution, and external tool calls.
- **Decision**: Use a Python FastAPI modular monolith (`apps/api`) rather than distributed microservices or Node.js.
- **Consequences**:
  - Direct access to Python AI/ML ecosystem, scraping tools, and asyncio libraries.
  - Zero inter-service network overhead during agent coordination.
  - High developer velocity and simplified deployment (single container).

## ADR-002: Abstracted Providers for LLM and Search

- **Status**: Accepted
- **Context**: Avoid vendor lock-in to OpenAI, Gemini, or specific search APIs (Tavily, SerpApi, DuckDuckGo), and enable zero-cost local testing.
- **Decision**: Introduce explicit interfaces `LLMProvider` and `SearchProvider` with first-class `MockProvider` implementations controlled by `MOCK_MODE=true`.
- **Consequences**:
  - The entire test suite and local dev run without external API keys.
  - Providers can be dynamically selected per query/depth configuration.

## ADR-003: SSE (Server-Sent Events) for Real-Time Agent Stream

- **Status**: Accepted
- **Context**: The user needs step-by-step visibility into agent reasoning, searches, claims, and contradictions.
- **Decision**: Utilize Server-Sent Events (`/api/research/{id}/events`) with Redis Pub/Sub backend dispatch rather than duplex WebSockets for research execution streaming.
- **Consequences**:
  - Simpler reconnect logic over standard HTTP.
  - Native browser `EventSource` support.
  - Reduced connection management complexity compared to full duplex WebSockets.

## ADR-004: SQLAlchemy 2.0 Asyncio with Alembic

- **Status**: Accepted
- **Context**: Async operations inside FastAPI with PostgreSQL.
- **Decision**: Use asyncpg driver with declarative SQLAlchemy 2.0 mapped models.
- **Consequences**: High concurrency support during multi-source extraction and background job updates.
