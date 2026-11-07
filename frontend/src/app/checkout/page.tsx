import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { CheckoutView } from "@/features/bookings/components/checkout-view";

export const metadata: Metadata = { title: "Checkout" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAuth>
          <CheckoutView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
