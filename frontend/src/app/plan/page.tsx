import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { PlanForm } from "@/features/planner/components/plan-form";
import { PlansList } from "@/features/planner/components/plan-view";

export const metadata: Metadata = { title: "Plan a trip", description: "Ranked flight and stay combinations." };

export default function PlanPage() {
  return (
    <div className="mx-auto grid w-full max-w-5xl gap-8 px-4 py-8">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <RequireAuth>
          <PlanForm />
          <PlansList />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
