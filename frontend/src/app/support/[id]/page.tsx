import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { PageHero } from "@/components/layout/page-hero";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { TicketView } from "@/features/support/support-views";

export const metadata: Metadata = { title: "Support request" };

export default function Page() {
  return (
    <>
      <PageHero title="Your request" eyebrow="We're here to help" image="/home/proof-landscape.png" position="5% 70%" overlap compact />
      <div className="tm-overlap mx-auto w-full max-w-4xl px-4 pb-10">
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <RequireAuth>
            <TicketView />
          </RequireAuth>
        </Suspense>
      </div>
    </>
  );
}
