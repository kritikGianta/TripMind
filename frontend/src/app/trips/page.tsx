import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { TripsView } from "@/features/bookings/components/trips-view";

export const metadata: Metadata = { title: "My Trips" };

export default function TripsPage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">My Trips</h1>
      <Suspense fallback={<Skeleton className="h-48 w-full" />}>
        <RequireAuth>
          <TripsView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
