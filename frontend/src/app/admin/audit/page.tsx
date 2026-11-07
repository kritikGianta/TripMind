import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAdmin } from "@/features/admin/components/require-admin";
import { AuditView } from "@/features/admin/components/analytics-view";

export const metadata: Metadata = { title: "Audit log" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAdmin>
          <AuditView />
        </RequireAdmin>
      </Suspense>
    </div>
  );
}
