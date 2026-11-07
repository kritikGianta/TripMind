import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { TripDetailView } from "@/features/bookings/components/trips-view";

export const metadata: Metadata = { title: "Trip" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAuth>
          <TripDetailView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
