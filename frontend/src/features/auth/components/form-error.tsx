import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { ApiError, errorMessage } from "@/lib/api/errors";

/** Form-level error. Shows the request ID so a failure can be traced in the API logs. */
export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  return (
    <Alert variant="destructive" role="alert">
      <AlertCircle aria-hidden />
      <AlertDescription>
        <span>{errorMessage(error)}</span>
        {requestId ? <span className="block text-xs opacity-70">Reference: {requestId}</span> : null}
      </AlertDescription>
    </Alert>
  );
}
