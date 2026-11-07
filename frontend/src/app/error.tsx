"use client";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto flex max-w-md flex-1 flex-col items-center justify-center gap-4 px-4 py-24 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="text-muted-foreground">Please try again. If it keeps happening, quote the reference below.</p>
      {error.digest ? <code className="rounded bg-muted px-2 py-1 text-xs">{error.digest}</code> : null}
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
