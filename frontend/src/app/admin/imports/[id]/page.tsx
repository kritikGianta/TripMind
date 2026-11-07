import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ImportReport } from "@/features/admin/components/import-report";
import { RequireAdmin } from "@/features/admin/components/require-admin";

export const metadata: Metadata = { title: "Import report" };

export default function ImportReportPage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAdmin>
          <ImportReport />
        </RequireAdmin>
      </Suspense>
    </div>
  );
}
