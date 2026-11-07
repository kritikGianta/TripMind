"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";

import { useSession } from "../hooks";

/**
 * Client-side guard for signed-in pages. The API enforces authorisation on every request; this
 * only decides what to render and sends signed-out visitors to sign-in, returning them afterwards.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      // Keep the query string: a checkout selection lives in the URL and must survive sign-in.
      router.replace(`/sign-in?next=${encodeURIComponent(pathname + window.location.search)}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <div className="grid gap-3" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  return <>{children}</>;
}
