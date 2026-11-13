"use client";

import { useQuery } from "@/lib/api/use-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

type DatasetSummary = Schemas["DatasetSummaryOut"];

const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

function formatDate(isoDate: string) {
  return dateFormat.format(new Date(`${isoDate}T00:00:00`));
}

/** States which dataset the catalog is serving, and flags synthetic demo data (blueprint rule). */
export function DatasetLabel() {
  const { data } = useQuery({
    queryKey: ["datasets", "current"],
    queryFn: () => apiFetch<DatasetSummary>("/holiday/window"),
    staleTime: 5 * 60_000,
  });
  if (!data || data.status !== "loaded") return null;

  const travel = data.travel_window;
  return (
    <p className="text-xs">
      {data.dataset}
      {travel ? ` · travel dates ${formatDate(travel.first_departure)} to ${formatDate(travel.last_departure)}` : null}
    </p>
  );
}
