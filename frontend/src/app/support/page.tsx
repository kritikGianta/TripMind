import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { PageHero } from "@/components/layout/page-hero";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { TicketsView } from "@/features/support/support-views";

export const metadata: Metadata = { title: "Support" };

export default function Page() {
  return (
    <>
      <PageHero title="Support" eyebrow="We're here to help" image="/home/proof-landscape.png" position="5% 70%" overlap />
      <div className="tm-overlap mx-auto w-full max-w-4xl px-4 pb-10">
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <RequireAuth>
            <TicketsView />
          </RequireAuth>
        </Suspense>
      </div>
    </>
  );
}
