import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHero } from "@/components/layout/page-hero";
import { Skeleton } from "@/components/ui/skeleton";
import { PlanModes } from "@/features/planner/components/plan-modes";

export const metadata: Metadata = { title: "Plan a trip", description: "Plan a flight and stay, or book a full holiday." };

export default function PlanPage() {
  return (
    <>
      <PageHero title="Plan a trip" eyebrow="One trip, one place" image="/home/way-plan.png" position="50% 45%" overlap />
      <div className="tm-overlap mx-auto grid w-full max-w-6xl gap-8 px-4 pb-10">
        <Suspense fallback={<Skeleton className="h-96 w-full" />}>
          <PlanModes />
        </Suspense>
      </div>
    </>
  );
}
