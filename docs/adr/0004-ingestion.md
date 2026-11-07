# ADR 0004: Catalog data enters only through a mapped, snapshot-based ingestion pipeline

- Status: accepted
- Date: 2026-11-07

## Context

The official dataset (hotels, flights, airports) arrives as a ZIP on finale day, in a format we have not seen. Until then we need realistic demo data. Bookings made against demo data must not break when the real data replaces it.

## Decision

1. **One path in.** Catalog tables are written only by the ingestion pipeline. The demo data is generated as files and imported like any supplier file; nothing is seeded into the catalog directly.
2. **Mapping as configuration.** A YAML mapping per dataset (`config/mappings/*.yaml`) names the file and the source column for each TripMind field, with optional format, scale, value map, default or constant. The profiler drafts a mapping for an unseen dataset.
3. **Stages:** read → extract (parse and validate each field, vectorised with pandas) → resolve (references, timezones, cities, derived rows, keys) → publish → report. The first three stages have no side effects, so a dry run is the same code path.
4. **Quarantine, not silent fixing.** A row that cannot be used is stored in `import_rejects` with a reason code (`MISSING_REQUIRED`, `INVALID_VALUE`, `OUT_OF_RANGE`, `DUPLICATE_KEY`, `UNKNOWN_REFERENCE`, `INCONSISTENT`), its file row number and its original values. A normalisation applied instead of a rejection (default capacity, assumed timezone, fuzzy city match) is counted in the report.
5. **Snapshot semantics with stable IDs.** IDs are UUIDv5 of a source key, so the same row always has the same ID. A content hash separates unchanged rows from updated ones. Rows missing from a newer import are retired (`is_active = false`), never deleted; flights and room types of retired airports and hotels are retired with them.
6. **Safety limits.** One import at a time (partial unique index on `status = 'running'`). If more than `max_reject_ratio` of an entity's rows is rejected, nothing is published. Publishing, the run report, the rejects and the audit record commit in one transaction.
7. **Provenance.** Every catalog row records `origin` (`provided`, `synthetic`, `derived`) and the import run that last wrote it. The public `/datasets/current` summary drives the UI's "Demo data" label.

## Consequences

- Swapping datasets on the day is: profile, edit the mapping, dry run, import. No code change unless the data needs a field TripMind does not model yet.
- Unknown fees or prices are not invented: missing fares and rates are stored as NULL and the product is browse-only.
- The pipeline holds a dataset in memory. That is fine for the expected size (the 24,000-row demo dataset imports in under 20 s in Docker), but files of millions of rows would need chunked publishing.
- Schedule-style flight data (days of week instead of dated rows) is not supported yet; it would be one more resolve step.
