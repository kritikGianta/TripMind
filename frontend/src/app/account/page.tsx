import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHero } from "@/components/layout/page-hero";
import { Skeleton } from "@/components/ui/skeleton";
import { AccountTabs } from "@/features/account/components/account-tabs";
import { RequireAuth } from "@/features/auth/components/require-auth";

export const metadata: Metadata = { title: "Account" };

export default function AccountPage() {
  return (
    <>
      <PageHero title="Account" eyebrow="Your details" image="/home/cta-landscape.png" position="12% 62%" overlap compact />
      <div className="tm-overlap mx-auto w-full max-w-5xl px-4 pb-10">
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <RequireAuth>
            <AccountTabs />
          </RequireAuth>
        </Suspense>
      </div>
    </>
  );
}
