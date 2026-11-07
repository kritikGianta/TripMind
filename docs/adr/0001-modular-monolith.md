# ADR 0001: Modular monolith

**Status:** Accepted

## Context

The hackathon rewards components connected end to end, and its problem statement is revealed on the day. A fleet of services adds networking, deployment and debugging cost without serving either goal.

## Decision

We run one FastAPI deployment, split internally into domain modules. Modules call each other only through services and protocols, never through another module's tables or repositories. The layer order is enforced by import-linter.

## Consequences

- **Pros:** one process to run, debug and demo.
- **Path to split:** the API is stateless and module seams are explicit, so search or planning can become separate services later if load or team ownership requires it.
- **Cost:** an import rule must be kept honest in CI.
