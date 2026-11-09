import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { ExtrasView } from "@/features/bookings/components/extras-view";

export const metadata: Metadata = { title: "Seats and extras" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <RequireAuth>
          <ExtrasView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
