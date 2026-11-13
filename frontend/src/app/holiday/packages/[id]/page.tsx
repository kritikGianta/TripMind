import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { PackageView } from "@/features/holiday/holiday";

export const metadata: Metadata = { title: "Holiday package" };

export default function HolidayPackagePage() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <PackageView />
      </Suspense>
    </div>
  );
}
