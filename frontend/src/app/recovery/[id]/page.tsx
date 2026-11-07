import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { RecoveryView } from "@/features/recovery/components/recovery-view";

export const metadata: Metadata = { title: "Trip change" };

export default function RecoveryPage() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <RequireAuth>
          <RecoveryView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
