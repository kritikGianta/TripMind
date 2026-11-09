import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHero } from "@/components/layout/page-hero";
import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { TripsView } from "@/features/bookings/components/trips-view";

export const metadata: Metadata = { title: "My Trips" };

export default function TripsPage() {
  return (
    <>
      <PageHero title="My Trips" eyebrow="Everything in one place" image="/home/dest-srinagar.png" overlap compact />
      <div className="tm-overlap mx-auto w-full max-w-5xl px-4 pb-10">
        <Suspense fallback={<Skeleton className="h-48 w-full" />}>
          <RequireAuth>
            <TripsView />
          </RequireAuth>
        </Suspense>
      </div>
    </>
  );
}
