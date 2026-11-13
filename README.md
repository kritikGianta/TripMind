# TripMind: Build My Holiday

TripMind is a travel booking website built for **Hackcellence 2026, Problem 1: Holiday Package → Build My Holiday**.

A traveller enters where they leave from, the country they want to visit, dates, who is travelling and a budget. TripMind chooses the cities and builds complete holiday packages: flights, hotels, transfers and attractions, laid out day by day. Every package is checked against every travel rule in the problem statement. The traveller can change any part, confirm, and reopen the trip later with a 10-digit reservation number.

**No AI, LLM or ML model is used anywhere in the app.** Packages come from rules, search and arithmetic, so every result can be explained.

---

## Quick start

You only need [Docker Desktop](https://www.docker.com/products/docker-desktop/). No `.env` file and no API keys.

```bash
git clone https://github.com/kritikGianta/TripMind-Hackcellence.git
cd TripMind-Hackcellence
docker compose up -d --build
```

Then open **http://localhost:3000**.

- The first build takes a few minutes. Loading the data takes about a minute more.
- The API documentation is at http://localhost:8000/docs.
- To stop the app, run `docker compose down`. Your data is kept.
- Ports 3000, 8000 and 5432 must be free.

On **Windows**, newer Docker versions can stop with `additional privileges requested: pass "--allow=fs.read=...Dockerfile"`. This is a known Docker issue. If you see it, run the build with the check turned off:

| Shell | Command |
|---|---|
| PowerShell | `$env:BUILDX_BAKE_ENTITLEMENTS_FS=0; docker compose up -d --build` |
| Git Bash, macOS or Linux | `BUILDX_BAKE_ENTITLEMENTS_FS=0 docker compose up -d --build` |

---

## Features

### Build My Holiday (the problem statement)

| ID | Feature | How TripMind does it |
|---|---|---|
| M1 | Request form | Seven fields. Departure cities and countries come from `destinations.json`. Invalid values get a clear message, for example "3 to 10 nights". |
| M2 | Build a package | Tries every valid city plan and builds complete packages. When none is possible, it says why: no flight that day, no free rooms, dates outside the data. |
| M3 | Rules respected | One rule checker (`engine.check`) tests every rule in section 4, on every build and every change. |
| M4 | Day-by-day plan | Flights, transfers, hotel check-ins and attractions in time order for each day. |
| M5 | Total and budget | Shows the total in INR, the budget and the amount left or over. **Download JSON** exports the package in the shared trip format (section 6). |
| M6 | Change the package | Swap a hotel, swap the arrival or return flight, add or remove attractions. The whole package is checked again, or the change is refused with the reason. |
| M7 | Confirm and reservation | Confirm gives a unique 10-digit number. **Reservation** in the menu opens it at any time, including after a restart. A wrong number shows "not found". |
| M8 | Budget too small | Says so, shows the cheapest possible total, and suggests a change (fewer nights, other dates, or a bigger budget). |
| G1 | Changes that affect other parts | After a change, items it affects are fixed or flagged, for example attraction times that no longer fit. |
| G2 | Price difference | Every change option shows its price difference against the current choice. |
| G4 | Three packages | The cheapest, the fastest (flight plus transfer time) and the best rated (average hotel stars per night, within budget). |
| S1 | Quick request | Type "me and my friend from Bangalore to Dubai tomorrow for 4 nights under 1.5 lakh" and the form fills itself. It is read with rules: regular expressions, word lists and typo matching, no AI. |
| S2 | Seats and rooms are used up | Confirming reserves seats and rooms in the database. If 20 people try to book the last seat, exactly one gets it. |

### More of the product (S3: our own ideas)

- **Plan a trip:** a flight and a stay together, ranked as one trip. It shares a page with Build My Holiday.
- **Flights, stays and Explore:** book each one on its own, or browse destinations by budget.
- **My Trips:** every booking and holiday in one place, each with a 10-digit reference.
- **Group trips:** share a trip, vote on options, and set budgets per person.
- **Disruption recovery:** when a flight is cancelled or badly delayed, the traveller chooses between rebooking and a refund. Only the affected part changes.
- **Change a booking:** pick another flight time or other stay dates, with the price difference shown.
- **Price alerts and loyalty points.**
- **No sign-up and no payment step:** a private guest session starts by itself, and confirming books the trip.

---

## Tech stack

| Part | Choice | Why |
|---|---|---|
| Backend | Python 3.12, **FastAPI** | Typed request and response models, automatic API docs |
| Database | **PostgreSQL 16** through **SQLAlchemy 2** and **Alembic** | Transactions and row locking make overselling impossible. Migrations version the schema. |
| Shared state | **Redis 7** | Rate limits shared by every API copy, and locks so a background job never runs twice |
| Background jobs | One worker process | Releases bookings that were never confirmed, re-checks price alerts, clears old data |
| Frontend | **Next.js 16**, React 19, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query | Fast pages, with typed API calls generated from the backend's OpenAPI schema |
| Running it | **Docker Compose** | One command starts the database, Redis, migrations, API, worker and website |

---

## How it works

### Data

- The official pack in `hackathon-problem-1-holiday-package/` is mounted read-only and **never changed**.
- `data/extended/` holds our extra data in **exactly the same schema**: more dates (13 Nov 2026 to 31 May 2027), more countries and more cities.
- On start-up, `python -m app.cli holiday load` loads both into PostgreSQL. Each record keeps its dataset ID, for example `FL-711`, so it can be traced. Running it again changes nothing.
- The location pickers only offer places that have data. Every departure city, destination and date the website lets you choose has flights and hotels.

### Building a package

The code is in `backend/app/modules/holiday/`.

1. **`engine.py`** loads a snapshot of the catalog.
2. `build()` lists every valid city plan for the country and the number of nights.
3. For each plan it picks flights, hotels that fit the party, transfers and attractions within opening hours.
4. `check()` tests the result against every rule. Only packages with **zero** broken rules are kept.
5. The cheapest, the fastest and the best rated are returned.

**`service.py`** saves packages, applies changes (re-checking everything) and confirms. **`quick.py`** is the rule-based quick request reader.

### Confirming without overselling

`backend/app/modules/inventory/service.py` reserves a seat or room with one conditional statement:

```sql
UPDATE flight_inventory SET reserved = reserved + :n
WHERE flight_id = :id AND reserved + :n <= capacity
```

PostgreSQL locks the row, so parallel buyers queue. One gets "1 row updated"; the rest get 0 rows and a `SOLD_OUT` message. Hotel stays update every night in one statement and are all-or-nothing. A database check constraint (`reserved <= capacity`) is the final safety net. On success, the reservation gets a random 10-digit number, made with `secrets`, unique and indexed.

### Request flow

```
Browser ──► Next.js (web :3000) ──/api/*──► FastAPI (api :8000) ──► PostgreSQL
                                                  │                    ▲
                                                  └──► Redis           │
                                    worker (scheduled jobs) ───────────┘
```

---

## API overview

All endpoints are under `/api/v1`. The full list is at http://localhost:8000/docs.

| Endpoint | Purpose |
|---|---|
| `GET /holiday/options` | Departure cities, countries and the travel window (M1) |
| `POST /holiday/parse` | Quick request: a sentence becomes form fields (S1) |
| `POST /holiday/packages` | Build the three packages (M2, M3, G4, M8) |
| `GET /holiday/packages/{id}/alternatives` | Change options with price differences (M6, G2) |
| `POST /holiday/packages/{id}/changes` | Apply a change and check everything again (M6, G1) |
| `POST /holiday/packages/{id}/confirm` | Reserve seats and rooms and get a 10-digit number (M7, S2) |
| `GET /holiday/reservations/{number}` | Open a reservation (M7) |
| `GET /holiday/packages/{id}/export` | Download as JSON (M5) |

---

## Tests

The tests cover what the problem statement asks for. Run them from `backend/`. You need [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run pytest
```

| File | What it proves |
|---|---|
| `tests/integration/test_holiday.py` | M1, M2/M3, M6, M7, M8 and S1, through the real API, using the handout's Menon family request |
| `tests/integration/test_holiday_pack.py` | The data pack loads completely and keeps its meaning, and reloading changes nothing |
| `tests/integration/test_bookings.py` | Guest booking, one-step confirm, the 10-digit reference, privacy, and that the last seat is sold only once |
| `tests/unit/test_shared_state.py` | Redis rate limits and job locks, including what happens when Redis is down |

The race test, with 20 buyers and one seat, runs on PostgreSQL. Set `TEST_DATABASE_URL` to enable it.

Code quality checks: `uv run ruff check .`, `uv run mypy app`, `uv run lint-imports` (enforces module layers), and `npm run typecheck && npm run lint` in `frontend/`.

---

## Project structure

```
hackathon-problem-1-holiday-package/   Official problem statement and data (read-only)
data/extended/                         Our extra data, in the same schema
config/                                Business rules and feature flags (YAML)
docs/                                  Operations notes and architecture decisions
backend/
  app/core/                            Settings, errors, security, rate limiting, Redis store
  app/modules/holiday/                 Build My Holiday: data loader, rule engine, quick request, API
  app/modules/inventory/               Seats and rooms: reserve and release without overselling
  app/modules/bookings/                Flight and stay bookings, changes, My Trips
  app/modules/<feature>/               Search, planner, groups, recovery, loyalty, watchlist, ...
  app/worker.py                        Background jobs
  migrations/                          Alembic database migrations
  tests/                               The tests listed above
frontend/
  src/app/                             Pages (Next.js App Router)
  src/features/<feature>/              API hooks and components per feature
  src/components/                      Shared UI
docker-compose.yml                     The whole stack
```

---

## Configuration

Nothing is needed to run locally. To deploy publicly, copy `.env.example` to `.env` and set your own `JWT_SECRET`, a random value of 32 or more characters. The built-in secret is for local use only, and the app refuses to start in production with it.

## Credits

- Data, hotel photos and attraction photos come from the Hackcellence 2026 data pack. Photo credits are in `hackathon-problem-1-holiday-package/images/ATTRIBUTIONS.md`.
- Home page images:
  - `ridge-landscape` and `ridge-far` show [Stok Kangri, Ladakh](https://commons.wikimedia.org/wiki/File:StokKangri.jpg), by Maverick34 (public domain).
  - Public domain NASA photographs from Wikimedia Commons:
    - [View of the Arabian Sea](https://commons.wikimedia.org/wiki/File:ISS036-E-48689_-_View_of_the_Arabian_Sea.jpg)
    - [India at night during Diwali 2012](https://commons.wikimedia.org/wiki/File:India_at_night_from_space_during_Diwali_2012.jpg)
    - ISS-62, city lights of Mumbai to Goa

> Built for Hackcellence 2026. Not affiliated with or endorsed by Booking Holdings or any travel provider.
