import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { JoinGroupView } from "@/features/groups/group-view";

export const metadata: Metadata = { title: "Join group" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAuth>
          <JoinGroupView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
