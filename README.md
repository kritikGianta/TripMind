# TripMind

TripMind is a travel booking website built for Hackcellence 2026, Problem 1: **Holiday Package, Build My Holiday**.

- **Build my holiday.** Pick a departure city, a country, dates, travellers and a budget. TripMind builds the cheapest, the fastest and the best-rated package (flights, hotels, transfers and attractions). Every package is checked against all the rules in the problem statement. You can change any part, confirm the package, and reopen it later with its 10-digit reservation number.
- **Plan a trip.** Book a flight and a stay together, both on the same page as Build my holiday.
- **Flights, stays and Explore.** Search and book each one on its own, or browse destinations by budget.
- **Extras.**
  - Group trips with voting.
  - Disruption recovery (rebook or refund when a flight is cancelled).
  - Changes to a booking.
  - Price alerts.
  - Loyalty points.

Every booking and holiday appears in **My Trips** with a 10-digit reference.

No AI, LLM or ML is used anywhere: packages come from rules and plain arithmetic. There is no sign-up (a private guest session starts by itself) and no payment step (confirming books the trip).

> Hackathon prototype. Not affiliated with or endorsed by Booking Holdings or any travel provider.

## Run it

You only need Docker Desktop. No `.env` file is required.

```bash
git clone https://github.com/kritikGianta/TripMind.git
cd TripMind
docker compose up -d --build
```

On Windows, recent Docker versions can stop with `additional privileges requested: pass "--allow=fs.read=...Dockerfile"`. If you see that, run the build like this instead:

| Shell | Command |
|---|---|
| PowerShell | `$env:BUILDX_BAKE_ENTITLEMENTS_FS=0; docker compose up -d --build` |
| Git Bash, macOS or Linux | `BUILDX_BAKE_ENTITLEMENTS_FS=0 docker compose up -d --build` |

The first build takes a few minutes.

- Website: http://localhost:3000
- API documentation: http://localhost:8000/docs

The site needs ports 3000, 8000 and 5432 to be free. To stop it, run `docker compose down`.

`migrate` runs first: it applies the database migrations and loads the data (about a minute). Then `api`, `worker` and `web` start.

For anything public, copy `.env.example` to `.env` and set your own `JWT_SECRET`. The built-in one is for local use only, and production refuses it.

| Service | What it does |
|---|---|
| `db` | PostgreSQL 16, which holds every booking and the catalog |
| `redis` | Shared rate limits and worker job locks |
| `migrate` | One-shot: migrations, demo accounts, then the data pack |
| `api` | FastAPI backend |
| `worker` | Scheduled jobs: price alerts, releasing unconfirmed bookings, data clean-up |
| `web` | Next.js frontend |

## Data

The official pack (`hackathon-problem-1-holiday-package/`) is never changed. Our extension, `data/extended/`, uses the same schema and adds more countries, cities and dates. `python -m app.cli holiday load` loads both, and running it again changes nothing. Each record keeps its dataset ID, so the official IDs (for example `FL-711`) can still be traced.

## How a holiday is built

The code is in `backend/app/modules/holiday/`.

| File | Role |
|---|---|
| `pack.py` | Loads the JSON files into the database |
| `engine.py` | `check()` tests a package against every rule. `build()` tries every valid city plan and keeps the cheapest, fastest and best rated |
| `service.py` | Builds, changes and confirms packages. Confirming reserves seats and rooms with a conditional update, so nothing is oversold |
| `quick.py` | Reads a sentence ("2 adults to Japan for 6 nights from Bengaluru") into the form, using rules only |
| `router.py` | The `/api/v1/holiday` endpoints |

## Tests

From the `backend/` folder:

```bash
uv run pytest                     # 19 tests on SQLite
uv run ruff check . && uv run mypy app && uv run lint-imports
```

| File | What it proves |
|---|---|
| `tests/integration/test_holiday.py` | Must-haves M1, M2/M3, M6, M7, M8 and S1, through the real API |
| `tests/integration/test_holiday_pack.py` | The pack loads completely, keeps its meaning, and reloading changes nothing |
| `tests/integration/test_bookings.py` | Guest booking, one-step confirm, 10-digit reference, privacy, and the last seat sold only once |
| `tests/unit/test_shared_state.py` | Redis rate limits and job locks, including what happens when Redis is down |

The 20-buyers-one-seat race test runs only on PostgreSQL. Set `TEST_DATABASE_URL` to run it.

After you change the API, regenerate the frontend types:

```bash
cd backend && uv run python -m app.cli openapi ../frontend/openapi.json
cd ../frontend && npm run gen:api && npm run typecheck && npm run lint
```

## Repository layout

```
hackathon-problem-1-holiday-package/   Official problem and data (read-only)
data/extended/          Our extra data, in the same schema
config/                 Feature flags and business rules (YAML)
docs/                   Operations notes and architecture decisions (adr/)
backend/
  app/core/             Settings, errors, security, rate limiting
  app/modules/<name>/   One folder per feature: router → service → models
  migrations/           Alembic migrations
  tests/                The tests listed above
frontend/
  src/app/              Pages
  src/features/<name>/  Feature code: API calls, hooks, components
  src/content/          Text for the Home and About pages
```

## Photo credits

- Destination photos on the home page come from the official data pack.
- `ridge-landscape` and `ridge-far` show [Stok Kangri, Ladakh](https://commons.wikimedia.org/wiki/File:StokKangri.jpg), by Maverick34 (public domain).
- These are public domain NASA photographs from Wikimedia Commons:
  - `route-opening`: [ISS036-E-48689, View of the Arabian Sea](https://commons.wikimedia.org/wiki/File:ISS036-E-48689_-_View_of_the_Arabian_Sea.jpg)
  - `route-origin`: [India at night from space during Diwali 2012](https://commons.wikimedia.org/wiki/File:India_at_night_from_space_during_Diwali_2012.jpg)
  - `route-destination`: ISS-62, City lights of Mumbai to Goa, India
