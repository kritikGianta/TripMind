# Operating TripMind

| Task | Command |
|---|---|
| Start everything | `docker compose up -d --build` |
| Stop, keeping data | `docker compose down` (adding `-v` deletes the database) |
| Check health | `curl http://127.0.0.1:8000/api/v1/ready` (database, migrations, Redis) |
| Reload the data pack | `docker compose run --rm migrate` (safe to repeat) |
| Regenerate our extension | `python -m app.cli holiday extend --start 2026-11-13 --end 2027-05-31` |

Run one `docker compose` command at a time. After changing backend code, rebuild the image (`docker compose build api`)
before you run commands in the container: `docker compose exec` runs the image's code, not your working copy.

## Reset the demo database

This deletes every booking and holiday, then reloads the data.

    docker compose stop api worker web
    docker compose exec db psql -U tripmind -d postgres -c "DROP DATABASE tripmind WITH (FORCE)" -c "CREATE DATABASE tripmind OWNER tripmind"
    docker compose run --rm migrate
    docker compose exec redis redis-cli FLUSHALL
    docker compose up -d --no-deps api worker web
