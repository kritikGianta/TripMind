# TripMind

TripMind is a travel booking website built for Hackcellence 2026, Problem 1: Holiday Package → Build My Holiday. You enter where you're leaving from, where you want to go, your dates, who's travelling and your budget. TripMind builds complete holiday packages (flights, hotels, transfers and attractions) and checks every travel rule. You can change any part, confirm, and open the trip later with a 10-digit reservation number.

You can also book flights or stays on their own, or plan a flight and a stay together.

## How to run it

You only need [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/kritikGianta/TripMind.git
cd TripMind
docker compose up -d --build
```

Open **http://localhost:3000**. The first start takes a few minutes while it builds and loads the data.

On a slow connection, a package download can still fail after the built-in retries. If that happens, run the same command again. Packages that already downloaded are kept, so it continues from where it stopped.

On Windows, if the build stops with `additional privileges requested: pass "--allow=fs.read=...Dockerfile"`, run this instead:

```powershell
$env:BUILDX_BAKE_ENTITLEMENTS_FS=0; docker compose up -d --build
```

To stop it, run `docker compose down`.
