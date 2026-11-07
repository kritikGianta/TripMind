/**
 * Every API failure becomes an `ApiError` carrying the backend's stable error `code`.
 * User-facing copy is chosen here, by code, so components never parse server messages.
 */

export type FieldError = { field: string; message: string; type: string };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;
  readonly requestId: string | undefined;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    details?: Record<string, unknown>;
    requestId?: string;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details;
    this.requestId = init.requestId;
  }

  get fieldErrors(): FieldError[] {
    const fields = this.details?.["fields"];
    return Array.isArray(fields) ? (fields as FieldError[]) : [];
  }
}

const MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "Email or password is incorrect.",
  EMAIL_TAKEN: "An account with this email already exists.",
  ACCOUNT_DISABLED: "This account has been disabled.",
  RATE_LIMITED: "Too many attempts. Please wait a minute and try again.",
  FEATURE_DISABLED: "This feature is not available right now.",
  DEMO_ACCOUNT_MISSING: "Demo accounts are not set up yet.",
  SESSION_EXPIRED: "Your session has ended. Please sign in again.",
  SESSION_REVOKED: "Your session has ended. Please sign in again.",
  NETWORK_ERROR: "We couldn't reach TripMind. Check your connection and try again.",
  INTERNAL: "Something went wrong on our side. Please try again.",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? error.message ?? MESSAGES.INTERNAL;
  }
  return MESSAGES.INTERNAL;
}
