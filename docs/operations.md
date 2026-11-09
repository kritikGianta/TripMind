# Operating TripMind

## Start, stop, update

| Task | Command |
|---|---|
| Start everything | `docker compose up -d --build` |
| With monitoring | `docker compose --profile obs up -d` (Grafana :3001, Prometheus :9090, Jaeger :16686) |
| Stop, keeping data | `docker compose down` (never add `-v` unless you mean to delete the database) |
| Check health | `curl http://127.0.0.1:8000/api/v1/ready` (database, migrations, Redis) |

After changing backend code, rebuild the image (`docker compose build api`) before running CLI
commands in the container: `docker compose exec` runs the image's code, not your working copy.

## Data

| Task | Command (inside the `api` container) |
|---|---|
| Profile a new dataset and draft a mapping | `python -m app.cli data profile <file> --write config/mappings/finale.yaml` |
| Check a dataset without publishing | `python -m app.cli data import <file> --mapping finale --dry-run` |
| Publish a dataset | `python -m app.cli data import <file> --mapping finale` |
| Regenerate the demo dataset | `python -m app.cli data generate --out /tmp/demo.zip`, then import with `synthetic-v1` |
| Fill the demo account with a story | `python -m app.cli demo-scenario` (`--fresh` sets the old demo account aside) |

Imports validate first and quarantine bad rows; too many rejects publishes nothing. A new import
updates fares and stays in place; existing bookings keep the prices they were booked at.

## Models

Files live in `models/<name>/artifacts/`, mounted read-only into the containers, and are picked up
on the next request. `GET /api/v1/admin/models` shows which are in use, with their metrics. Removing
a model's files, or switching its flag off in `config/features.yaml`, falls back to rules. The
traveller flows never depend on a model being present.

## Home page photos and videos

Save a file as `frontend/public/home/<slot>.<ext>` and it replaces that slot's placeholder. Images:
jpg, jpeg, png, webp, avif. Video: mp4, webm; an image with the same name becomes its poster. Slots
and what each one should show are listed in `frontend/src/content/home.ts`. `npm run dev` picks files
up on refresh; a Docker or production build needs rebuilding (`docker compose build web`).

The original files as supplied stay in `Images&Videos/` (git-ignored). `hero-film.mp4` is a 1080p ffmpeg
encode of `main-homepage-video.mp4`, 5.4 MB instead of 29.8 MB, with its last 2 s crossfaded into its start so
the loop has no visible jump; `hero-film.jpg` is its first frame. Re-encoding a video? Do not record a canvas
with MediaRecorder: that froze the picture while the timer kept running. The e2e suite now compares pixels. `ridge-landscape` and `ridge-far` are [Stok Kangri, Ladakh](https://commons.wikimedia.org/wiki/File:StokKangri.jpg) by Maverick34, public domain, cut out along the peak's real outline against the sky; the far range is the same peak, hazed. The hero's clouds (`fog-back`, `fog-front`) are generated, so they have no source to credit. Next's image server caches by file name for about a minute, so a replaced image can look unchanged at first.

Three home images are public domain NASA photographs from Wikimedia Commons, recoloured or cropped for the page:
`route-opening` is [ISS036-E-48689, View of the Arabian Sea](https://commons.wikimedia.org/wiki/File:ISS036-E-48689_-_View_of_the_Arabian_Sea.jpg),
`route-origin` is [India at night from space during Diwali 2012](https://commons.wikimedia.org/wiki/File:India_at_night_from_space_during_Diwali_2012.jpg),
and `route-destination` is ISS-62, City lights of Mumbai to Goa, India. Replacing one means saving a file under
the same name after deleting the old one, because the first match wins, and updating that slot's `alt` in `home.ts`.

Home and About share one Motion switch (`features/motion/use-motion.ts`). Never write a value that changes every
frame to a page-wide element: restyling the whole page cost Home half its frame rate.

## Frontend work without Docker

Docker is not needed day to day for UI work. Quit Docker Desktop, then in two terminals:

    powershell -ExecutionPolicy Bypass -File scripts\local-api.ps1
    cd frontend; npm run dev

The API then uses `backend/local-dev.db`, a git-ignored copy of a loaded demo database, and the repo's `.env`.
There is no worker, Redis or monitoring, so background jobs do not run. Test the Docker stack
(`docker compose up -d --build web`) whenever a section is finished and before any demo: it is the real
PostgreSQL setup, and the only place to catch problems that SQLite hides.

## If Docker Desktop stops answering

If `127.0.0.1:3000` gives an empty reply while `docker ps` shows healthy containers, the engine has
restarted and its port forwarding is stale. `docker compose up -d --force-recreate --no-deps web api`
restores it without a rebuild.

## Background worker

One `worker` container runs `app/worker_jobs.py`; each job holds a Redis lock, so extra workers
cannot double-run it. `worker:9100/metrics` is its health signal.

| Job | Every | What it does |
|---|---|---|
| `expire_holds` | 30 s | Releases unpaid holds |
| `check_price_alerts` | 30 min | Re-prices alerts and notifies once |
| `train_preferences` | 60 min | Refits travellers with new activity |
| `purge_expired_data` | 24 h | Applies the retention periods in `config/rules.yaml` |

## Security settings for a real deployment

- Set `ENVIRONMENT=production`, a random `JWT_SECRET` of 32+ characters and `COOKIE_SECURE=true`;
  the app refuses to start otherwise.
- Demo login is forced off in production. Create admins with `python -m app.cli create-admin`.
- `dev_reset_token` is only returned in `local` and `test`. Elsewhere a real email provider must
  replace the simulated email channel (`notifications/service.py`, `auth.forgot_password`).
- Payments are a simulator. A real provider would replace `bookings/payments.py`.

## Backup and restore

```bash
docker compose exec -T db pg_dump -U tripmind tripmind > backup.sql
docker compose exec -T db psql -U tripmind tripmind < backup.sql
```

## When something is wrong

| Symptom | Look at |
|---|---|
| A user reports an error | Search logs for the `request_id` shown in the error, then `/admin/audit` |
| `/ready` says migrations are behind | The `migrate` container's logs; `alembic upgrade head` |
| Redis is down | Rate limits and caches fail open; job locks fail closed, so jobs pause until it returns |
| AI answers show `rules` as the source | `GET /api/v1/ai/status`; providers cool down after errors and search still works |
| Ports stop answering after a Docker restart | `docker compose up -d --force-recreate` |
