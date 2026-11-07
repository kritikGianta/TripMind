/**
 * The single HTTP client for the TripMind API.
 *
 * - Same-origin requests to `/api/v1/*`; Next.js proxies them to FastAPI (see next.config.ts),
 *   so session cookies are httpOnly and never touched by JavaScript.
 * - Errors are normalised into `ApiError` from the backend's error envelope.
 * - An expired access token is refreshed once, transparently, and the request retried.
 *   Concurrent requests share one in-flight refresh.
 */
import { ApiError } from "./errors";
import type { components } from "./schema";

export type Schemas = components["schemas"];

export const API_BASE = "/api/v1";

const REFRESHABLE = new Set(["TOKEN_EXPIRED", "AUTH_REQUIRED", "TOKEN_INVALID"]);
const NO_REFRESH_PATHS = new Set(["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout", "/auth/demo-login"]);

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type RequestOptions = {
  method?: Method;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    credentials: "same-origin",
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("x-request-id") ?? undefined;
  try {
    const payload = (await response.json()) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown>; request_id?: string };
    };
    const error = payload.error;
    if (error?.code) {
      return new ApiError({
        status: response.status,
        code: error.code,
        message: error.message ?? response.statusText,
        details: error.details,
        requestId: error.request_id ?? requestId,
      });
    }
  } catch {
    // Non-JSON body (for example a proxy error page); fall through.
  }
  return new ApiError({
    status: response.status,
    code: response.status >= 500 ? "INTERNAL" : "HTTP_ERROR",
    message: response.statusText || "Request failed",
    requestId,
  });
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  try {
    return await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
      cache: "no-store",
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError({ status: 0, code: "NETWORK_ERROR", message: "Network request failed" });
  }
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);

  if (response.status === 401 && !NO_REFRESH_PATHS.has(path)) {
    const error = await toApiError(response.clone());
    if (REFRESHABLE.has(error.code) && (await refreshSession())) {
      response = await send(path, options);
    }
  }

  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
