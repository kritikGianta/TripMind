# ADR 0002: PostgreSQL is the only required store

**Status:** Accepted

## Context

Booking correctness needs transactions, constraints and conditional updates. Redis, a vector database and a search engine are each useful, but none is required for correctness.

## Decision

PostgreSQL holds all state: users, catalog, inventory, holds, bookings, idempotency keys and audit records. Redis and pgvector are optional adapters behind interfaces. With them off, the cache is in-process and vector search is in memory or keyword-based.

## Consequences

- **Correctness:** it never depends on a cache; holds and idempotency survive restarts.
- **Fallback:** SQLite remains an emergency fallback. This is why money is stored as integer minor units and no PostgreSQL-only query features are used in the core.
