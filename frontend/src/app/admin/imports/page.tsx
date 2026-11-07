import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ImportsView } from "@/features/admin/components/imports-view";
import { RequireAdmin } from "@/features/admin/components/require-admin";

export const metadata: Metadata = { title: "Data imports" };

export default function ImportsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAdmin>
          <ImportsView />
        </RequireAdmin>
      </Suspense>
    </div>
  );
}
