import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ReservationView } from "@/features/holiday/holiday";

export const metadata: Metadata = { title: "Reservation" };

export default function ReservationPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <ReservationView />
      </Suspense>
    </div>
  );
}
