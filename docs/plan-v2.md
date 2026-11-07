# TripMind: Engineering Plan v2

Plan v2 replaces the gap list and open decisions in v1 (`TripMind — Engineering Plan & System Design.docx`). v1 still applies wherever this document is silent. Read `PROJECT_MEMORY.md` in the project folder for the full decision history.

## 1. What we are building

TripMind is a travel-booking platform with three entry modes over one set of services:

1. **Flight-only booking:** search, compare, hold, pay (simulated), confirm.
2. **Hotel-only booking:** the same flow for stays.
3. **Connected-trip planning:** the optional AI-assisted mode. It plans a flight and a stay together, ranks complete bundles, and books them through the same booking engine.

Every booking appears in **My Trips**. A trip can start with one product and gain the other later. With every AI feature switched off, TripMind is still a complete travel application.

## 2. Architecture

- **Shape:** a modular monolith. Next.js (TypeScript) talks to one FastAPI service; PostgreSQL is the only required store.
- **Runtime:** Docker Compose. Next.js rewrites `/api/*` to FastAPI, so the browser sees one origin and authentication can use httpOnly cookies without CORS.
- **Backend layering inside every module:**
  - Router: HTTP only.
  - Service: one method per use case; owns the transaction.
  - Domain rules: pure Python.
  - Repository: SQLAlchemy queries; owner filter on every user-owned query.
- **Plug-ins:** sit behind protocols and are chosen by configuration. This covers ranking, intent parsing, LLM providers, cache, payments and embeddings.
- **Configuration:** anything the finale can change lives in `config/*.yaml`, overridable by environment variables: column mappings, filters, business rules, ranking weights and feature flags.
- **Transactions:** sync SQLAlchemy 2.0, one unit of work per request. Concurrency safety comes from conditional `UPDATE`s plus unique constraints, not application locks.

## 3. Resolutions of the v1 gaps

| Gap | Resolution |
|---|---|
| G2 `/ready` deadlock | `/ready` checks only the database connection and that migrations are at head. Dataset state is reported separately in the admin import report, never in health checks. |
| G3 dependency rule | Layers: `core/db/shared` → `catalog, pricing, inventory` → `verticals` → `bookings, trips` → `planner` → `recovery` → `admin`. `main.py` and `core/deps.py` are the composition root and may import plug-ins. Enforced with import-linter. |
| G4 flags vs types | Disabled features keep their routes but return `404 FEATURE_DISABLED` in the error envelope. TypeScript types are generated with every flag on, so the frontend contract never depends on flags. |
| G5 SQLite fallback | Money is stored as integer minor units plus a currency code. Amenities use a join table, not JSON queries. Upserts go through one dialect-aware helper. |
| G6 recovery model | Tables `disruption_events`, `recovery_proposals` and `refunds`. A booking item can be replaced by another item, so a cancelled flight never touches the hotel in the same booking. |
| G7 plan persistence | `trip_plans` stores the intent, the candidate bundles (JSON snapshot) and saved or dismissed options. |
| G8 travellers | `traveller_profiles` (saved by users) and `booking_travellers` (a snapshot per booking). Checkout has a traveller-details step. Synthetic travellers are used until real data exists. |
| G9 return and 1-stop | An **Offer** is an ordered list of legs (flight segments or hotel nights). Bookings reserve offers, so a return or connecting itinerary holds all its legs or none. |
| G10 hotel holds | Inventory rows are created lazily per hotel-night and unique per (room type, date). A stay reserves every night in one statement and checks the affected-row count. The claim is stored so it can be released. |
| G11 currencies | Static, labelled FX rates in `config/rules.yaml`; ledgers show the original currency and the converted total. |
| G12 timezones | Local time is stored alongside UTC. Missing airport timezones fall back to a configured default timezone. |
| G13 past dates | The valid travel window is derived from the dataset; the injectable clock can be pinned for demos. |
| G14 missing prices | A labelled estimate (rate estimator), or the item is browse-only. Values are never silently invented. |
| G15 re-import | Deterministic IDs from source keys; rows missing from a new import are retired, not deleted. Bookings keep price snapshots. |
| G16 large files | Chunked, vectorised validation; a large synthetic fixture is part of the test suite. |
| G17 transactions | Sync SQLAlchemy, one session per request; the concurrency test uses real threads against PostgreSQL. |
| G18 idempotency race | Unique `(user_id, idempotency_key)` inserted inside the hold transaction. |
| G19 login mid-checkout | The selection lives in the URL and the session draft; sign-in redirects back with `next=`. One-click demo login sits behind a feature flag. |

## 4. Authentication (built first)

- **Accounts:**
  - Email and password. Email is normalised to lowercase and unique.
  - Passwords: 8 to 128 characters, no composition rules (NIST SP 800-63B), hashed with Argon2id. Hashes are upgraded on login when parameters change.
- **Sessions:**
  - **Access token:** a short-lived JWT (15 min) in an httpOnly cookie.
  - **Refresh token:** an opaque random token (7 days) in an httpOnly cookie scoped to `/api/v1/auth`. It is stored only as a SHA-256 hash and rotated on every use.
  - **Reuse detection:** reusing a rotated refresh token revokes the whole token family.
- **CSRF:** cookies are `SameSite=Lax` and mutating endpoints accept JSON only, so cross-site form posts cannot authenticate.
- **Abuse protection:** per-IP and per-account rate limits on sign-in, sign-up, refresh and demo login. Unknown emails take the same time to reject as wrong passwords.
- **Authorisation:** roles `traveler` and `admin`. Every user-owned query filters by the owner, so another user's ID returns 404.
- **Audit:** every authentication event (success and failure) is written to `audit_log` with request ID, IP and user agent.
- **Demo login:** for judges, behind the `demo_login` flag. The application refuses to start with it enabled when `ENVIRONMENT=production`.

## 5. Observability

- **Always on:** JSON logs with request IDs; `X-Request-ID` on every response; `/metrics` (Prometheus format) on the API's internal port only; `/api/v1/health` (liveness) and `/api/v1/ready` (readiness).
- **Optional `obs` profile:** Prometheus, Grafana (dashboards and alert rules stored as code) and OpenTelemetry with Jaeger. The app never depends on them.
- **Rules:** dashboards show domain signals: zero-result searches, booking conflicts, import rejects, AI fallbacks and latency. User and booking IDs are never metric labels.

## 6. AI and models

- **Hosted LLMs:** free API keys tried in order (Groq → Gemini → OpenRouter) with timeouts, failover on rate limits, response caching and rule-based fallbacks.
- **Small models on CPU:**
  - Hotel ranker and fare estimator, trained in Kaggle notebooks.
  - Review sentiment, hotel rate estimator, similar hotels, request classifier, import anomaly detector and preference model.
- **Safeguards:** every model sits behind an interface with a deterministic fallback and a feature flag. AI never confirms, cancels or pays; the traveller does.

## 7. Build order

Each step ends runnable, tested and committed.

1. Plan v2, repository layout, Docker Compose, CI.
2. **Authentication service** (FastAPI + PostgreSQL + Alembic).
3. **Frontend shell:** navbar, sign-in and sign-up, account page, typed API client.
4. **Home page.**
5. **About page:** the presentation deck, driven by a single content file.
6. Synthetic data generator + ingestion pipeline (profiler, mappings, validation, quarantine, import report).
7. Flight and hotel search (filter registry, offers, pricing ledger).
8. Booking engine (offers, holds, idempotency, payments simulator, travellers) and My Trips.
9. Connected-trip planner, ranking, Journey Confidence Report, add-on booking.
10. Disruption and recovery.
11. AI plug-ins: NL search, assistant, RAG, group planning, small models.
12. Platform features: extras, notifications, documents, loyalty, promotions, reviews, admin console.
13. Observability stack, load script, hardening, finale playbook.
