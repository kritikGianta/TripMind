# ADR 0003: httpOnly cookie sessions with rotating refresh tokens

**Status:** Accepted

## Context

v1 proposed a bearer JWT held by the browser. A token readable by JavaScript is exposed to any cross-site scripting (XSS) bug. Next.js also cannot read it during server rendering.

## Decision

- **Origin:** the frontend proxies `/api/*` to FastAPI, so the API shares the web origin.
- **Access token:** a 15-minute JWT in an `httpOnly`, `SameSite=Lax` cookie.
- **Refresh token:** an opaque random value in a cookie scoped to `/api/v1/auth`. It is stored server-side only as a SHA-256 hash and rotated on each use; reuse of a rotated token revokes its family.

## Consequences

- **XSS:** page scripts cannot read or steal tokens.
- **Revocation:** sign-out and theft response work because refresh tokens are revocable server-side.
- **CSRF:** mitigated by `SameSite=Lax` plus JSON-only mutating endpoints; a CSRF token is required if `SameSite=None` is ever used.
- **Proxy dependency:** API clients other than the web app must go through the same origin or present the cookie.
