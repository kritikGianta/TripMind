import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { HotelResultsView } from "@/features/search/components/hotel-results";

export const metadata: Metadata = { title: "Stays", description: "Search hotels by city, dates and guests." };

export default function StaysPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto my-8 h-40 w-full max-w-6xl" />}>
      <HotelResultsView />
    </Suspense>
  );
}
