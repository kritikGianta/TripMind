# TripMind

TripMind is a travel booking platform with three ways in:

1. Book a flight on its own.
2. Book a stay on its own.
3. Plan both together as one connected trip.

Every booking lands in **My Trips**. AI helps when it is switched on, and the platform works fully without it.

> Hackathon prototype for Hackcellence 2026. Not affiliated with or endorsed by Booking Holdings or any travel provider.

## What runs today

| Area | Status |
|---|---|
| Accounts: sign-up, sign-in, sign-out, one-click demo access, account page | Live |
| Session security: Argon2id, httpOnly cookies, rotating refresh tokens, reuse detection, rate limits, audit log | Live |
| Platform: error contract, request IDs, health and readiness checks, Prometheus metrics, feature flags | Live |
| Web app: navbar, home page, About page (presentation deck) | Live |
| Data ingestion, search, booking engine, trip planner, recovery, AI assistant, dashboards | Planned (see [plan v2](docs/plan-v2.md)) |

## Quick start (Docker)

```bash
cp .env.example .env            # then set JWT_SECRET (command is in the file)
docker compose up -d --build
```

- App: http://localhost:3000. Use **Demo access → Traveller** on the sign-in page.
- API docs: http://localhost:8000/api/v1/docs
- Readiness: http://localhost:8000/api/v1/ready
- Metrics: http://localhost:8000/metrics

`migrate` applies database migrations and creates the demo accounts, then exits; `api` and `web` start once it succeeds.

## Local development

```bash
docker compose up -d db

cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed
uv run uvicorn app.main:create_app --factory --reload      # http://127.0.0.1:8000

cd ../frontend
npm install
npm run dev                                                 # http://localhost:3000
```

## Quality checks

| Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|
| `uv run pytest` (SQLite) | `npm run lint` |
| `TEST_DATABASE_URL=postgresql+psycopg://tripmind:tripmind@127.0.0.1:5432/tripmind_test uv run pytest` | `npm run typecheck` |
| `uv run ruff check . && uv run mypy app` | `npm run build` |
| `uv run lint-imports` (enforces module layering) | `npm run gen:api` (regenerate API types) |

After changing the API, regenerate the frontend types:

```bash
cd backend && uv run python -m app.cli openapi ../frontend/openapi.json
cd ../frontend && npm run gen:api
```

## Repository layout

```
config/                 Runtime configuration (feature flags; mappings and rules as they land)
docs/                   plan-v2.md and architecture decision records (adr/)
backend/
  app/core/             Settings, errors, logging, security, metrics, rate limiting, dependencies
  app/db/               SQLAlchemy base and session lifecycle
  app/modules/<name>/   One folder per domain: router → service → repository → models
  migrations/           Alembic migrations
  tests/                Unit and API tests (SQLite and PostgreSQL)
frontend/
  src/app/              Routes (App Router)
  src/features/<name>/  Feature code: API calls, hooks, components
  src/components/       Shared UI (shadcn/ui primitives, layout)
  src/content/about.ts  The About deck's content (single source of truth)
  src/lib/api/          Typed API client, error handling, generated schema
```

## AI provider keys (optional)

The app runs without them. Add any you have to `.env`:

| Provider | Variable | Get a key |
|---|---|---|
| Groq | `GROQ_API_KEY` | https://console.groq.com/keys |
| Google Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/settings/keys |

Free tiers have rate limits and may use submitted content to improve their models, so TripMind never sends travellers' personal details to them.
