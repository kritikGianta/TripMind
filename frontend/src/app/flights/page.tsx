import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { FlightResultsView } from "@/features/search/components/flight-results";

export const metadata: Metadata = { title: "Flights", description: "Search one-way and return flights." };

export default function FlightsPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto my-8 h-40 w-full max-w-6xl" />}>
      <FlightResultsView />
    </Suspense>
  );
}
