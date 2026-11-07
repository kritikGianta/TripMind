import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { InvoiceView } from "@/features/bookings/components/invoice-view";

export const metadata: Metadata = { title: "Invoice" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAuth>
          <InvoiceView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
