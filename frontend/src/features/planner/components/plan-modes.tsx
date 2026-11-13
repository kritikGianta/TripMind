"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RequireAuth } from "@/features/auth/components/require-auth";
import { HolidayPlanner } from "@/features/holiday/holiday";

import { PlanForm } from "./plan-form";
import { PlansList } from "./plan-view";

/**
 * One page, two ways to plan: "Plan a trip" (flight + stay, ranked) or "Book my holiday" (TripMind
 * picks the cities and builds a full package). The choice lives in the URL (?mode=holiday).
 */
export function PlanModes() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const mode = params.get("mode") === "holiday" ? "holiday" : "trip";
  return (
    <Tabs value={mode} onValueChange={(value) => router.replace(value === "holiday" ? `${pathname}?mode=holiday` : pathname, { scroll: false })} className="grid gap-6">
      <TabsList className="w-fit">
        <TabsTrigger value="trip">Plan a trip · flight + stay</TabsTrigger>
        <TabsTrigger value="holiday">Book my holiday · full package</TabsTrigger>
      </TabsList>
      <TabsContent value="trip" className="grid gap-8">
        <RequireAuth>
          <PlanForm />
          <PlansList />
        </RequireAuth>
      </TabsContent>
      <TabsContent value="holiday">
        <HolidayPlanner />
      </TabsContent>
    </Tabs>
  );
}
