import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { GroupView } from "@/features/groups/group-view";

export const metadata: Metadata = { title: "Group trip" };

export default function Page() {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAuth>
          <GroupView />
        </RequireAuth>
      </Suspense>
    </div>
  );
}
