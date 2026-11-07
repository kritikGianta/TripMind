import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { HotelDetailPage } from "@/features/search/components/hotel-detail-page";

export const metadata: Metadata = { title: "Stay details" };

export default function StayDetailPage() {
  return (
    <Suspense fallback={<Skeleton className="mx-auto my-8 h-64 w-full max-w-5xl" />}>
      <HotelDetailPage />
    </Suspense>
  );
}
