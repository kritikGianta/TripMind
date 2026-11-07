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
| Web app: navbar, home page, About page (presentation deck), dataset label | Live |
| Data: catalog schema, ingestion pipeline (profile, map, validate, quarantine, publish, report), synthetic demo dataset, admin import API | Live |
| Search: airports and cities with aliases, flights (direct and one-stop, one-way or return), stays by party size, hotel details, filters with counts, sorting, itemised prices, currency conversion | Live |
| Admin data console: upload, dry run, import history, report and quarantined rows (`/admin/imports`) | Live |
| Bookings: checkout with traveller details, 15-minute holds on seats and rooms, idempotent requests, simulated card payments (4242 4242 4242 4242 succeeds, 4000 0000 0000 0002 declines), item-level cancellation with refunds, My Trips with add-on bookings | Live |
| Connected-trip planner (`/plan`): ranked flight + stay bundles with weights from `config/ranking.yaml`, an explanation and a Journey Confidence Report per option, saved/dismissed decisions, one-checkout booking | Live |
| Disruption recovery: admin **Disruptions** console (cancel or delay a booked flight, take a room out of service), affected bookings found, unpaid holds released, travellers notified and offered rebooking or a refund; only the affected item is replaced | Live |
| Notifications: in-app bell with simulated email copies | Live |
| Monitoring (optional `obs` profile): Prometheus with alert rules, Grafana dashboard as code, OpenTelemetry traces in Jaeger; synthetic load script | Live |
| Account: saved travellers (prefill checkout), loyalty points (earned on payment, reversed on refund), printable invoice | Live |
| Promo codes from `config/promotions.yaml` (WELCOME10, STAYLONGER, TRIPTOGETHER), priced on the server | Live |
| Admin console: data imports, disruptions, analytics, audit log | Live |
| AI: "Describe your trip" search (LLM + rule parser, grounded in the catalog), **Ask TripMind** help assistant (BM25 retrieval over help and policies generated from config, cites sources, never acts). Providers in `config/ai.yaml` tried in order with cooldowns, cache and redaction; rules when none answers | Live |
| Group planning, trained small models | Planned |

## Quick start (Docker)

```bash
cp .env.example .env            # then set JWT_SECRET (command is in the file)
docker compose up -d --build
```

- App: http://localhost:3000. Search flights or stays from the home page. Sign in with **Demo access → Admin** to open **Data imports** from the account menu.
- API docs: http://localhost:8000/api/v1/docs
- Readiness: http://localhost:8000/api/v1/ready
- Metrics: http://localhost:8000/metrics

`migrate` applies database migrations, creates the demo accounts and, on first start, generates the synthetic demo dataset and imports it through the normal pipeline (about 30 s; skip with `BOOTSTRAP_DEMO_DATA=false`). It then exits; `api` and `web` start once it succeeds.

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

## Data

Catalog data (airports, flights, hotels, room types) is only ever loaded through the ingestion pipeline, from a ZIP or folder of CSV, TSV, JSON, JSONL or XLSX files. A YAML mapping in `config/mappings/` says which column feeds which TripMind field ([ADR 0004](docs/adr/0004-ingestion.md)).

```bash
cd backend
uv run python -m app.cli data generate                       # ../data/generated/synthetic-v1.zip
uv run python -m app.cli data import ../data/generated/synthetic-v1.zip --mapping synthetic-v1 --dry-run
uv run python -m app.cli data import ../data/generated/synthetic-v1.zip --mapping synthetic-v1
```

Swapping in a new dataset (for example the finale data):

1. `uv run python -m app.cli data profile finale.zip --dataset finale --write ../config/mappings/finale.yaml` drafts a mapping and comments every uncertain guess.
2. Review the mapping, then import with `--dry-run` and read the report.
3. Import for real. Rows the new file no longer contains are retired, not deleted.

Each import reports, per entity: rows read, accepted, rejected (with reason codes), inserted, updated, unchanged and retired. It also lists the normalisations applied (defaults filled, timezones assumed, fuzzy city matches). Rejected rows are kept with their file row number and original values. If more than 20% of an entity's rows are rejected, nothing is published (`config/rules.yaml`).

Admins can do the same over HTTP: `/api/v1/admin/imports` (upload, dry run, history), `/admin/imports/{id}/rejects` and `/admin/imports/profile`. Uploads need the `X-Requested-With: tripmind` header. `GET /api/v1/datasets/current` is public and drives the "Demo data" label in the footer.

## Monitoring (optional)

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318 docker compose --profile obs up -d
cd backend && uv run python scripts/loadtest.py --base-url http://localhost:8000 --users 8 --duration 60
```

- Grafana: http://localhost:3001 (opens on the **TripMind overview** dashboard; anonymous viewer)
- Prometheus: http://localhost:9090 (Alerts tab shows the rules in `ops/prometheus/alerts.yml`)
- Jaeger: http://localhost:16686 (service `tripmind-api`; each request shows its SQL statements)

Dashboards are code: edit `ops/grafana/build_dashboard.py`, run it, commit the JSON. Metrics use small label sets (no user or booking IDs). The app runs the same with the stack off.

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
config/                 Feature flags, business rules, vocabularies, dataset mappings (mappings/)
docs/                   plan-v2.md and architecture decision records (adr/)
backend/
  app/core/             Settings, errors, logging, security, metrics, rate limiting, dependencies
  app/db/               SQLAlchemy base and session lifecycle
  app/modules/<name>/   One folder per domain: router → service → repository → models
  app/datagen/          Synthetic demo dataset generator (writes files, never the database)
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
