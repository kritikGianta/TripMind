import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAdmin } from "@/features/admin/components/require-admin";
import { OperationsView } from "@/features/recovery/components/operations-view";

export const metadata: Metadata = { title: "Disruptions" };

export default function OperationsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAdmin>
          <OperationsView />
        </RequireAdmin>
      </Suspense>
    </div>
  );
}
