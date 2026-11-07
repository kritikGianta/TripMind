import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { PlanView } from "@/features/planner/components/plan-view";

export const metadata: Metadata = { title: "Trip plan" };

export default function PlanResultPage() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <RequireAuth>
          <PlanView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
