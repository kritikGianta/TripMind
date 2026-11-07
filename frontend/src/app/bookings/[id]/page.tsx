import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { BookingView } from "@/features/bookings/components/booking-view";

export const metadata: Metadata = { title: "Booking" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAuth>
          <BookingView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
