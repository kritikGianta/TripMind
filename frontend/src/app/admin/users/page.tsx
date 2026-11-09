import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { RequireAdmin } from "@/features/admin/components/require-admin";
import { UsersView } from "@/features/admin/components/models-users-views";

export const metadata: Metadata = { title: "Users" };

export default function Page() {
  return (
    <div className="mx-auto grid w-full max-w-6xl gap-4 px-4 py-8">
      <h1>Users</h1>
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RequireAdmin>
          <UsersView />
        </RequireAdmin>
      </Suspense>
    </div>
  );
}
