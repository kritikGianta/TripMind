import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHero } from "@/components/layout/page-hero";
import { Skeleton } from "@/components/ui/skeleton";
import { ExploreView } from "@/features/search/components/explore-view";

export const metadata: Metadata = { title: "Explore", description: "Where a budget can take you, with flight and stay totals." };

export default function ExplorePage() {
  return (
    <>
      <PageHero title="Where could you go?" eyebrow="Explore" text="Flights and a stay, added up for every city in the data." image="/home/dest-opening.png" overlap />
      <div className="mx-auto w-full max-w-6xl px-4 pb-10">
        <Suspense fallback={<Skeleton className="tm-overlap h-40 w-full" />}>
          <ExploreView />
        </Suspense>
      </div>
    </>
  );
}
