/**
 * Only same-site relative paths are accepted as post-sign-in destinations, so a crafted
 * `?next=https://evil.example` link cannot redirect users off TripMind (open-redirect guard).
 */
export function safeNextPath(value: string | null | undefined, fallback = "/"): string {
  if (!value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  return value;
}
