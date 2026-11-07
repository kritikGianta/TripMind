"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

type Features = Schemas["FeaturesOut"]["features"];

/** Backend feature flags; UI for a disabled feature is hidden, never shown broken. */
export function useFeatures() {
  const query = useQuery({
    queryKey: ["meta", "features"],
    queryFn: () => apiFetch<Schemas["FeaturesOut"]>("/meta/features"),
    staleTime: 5 * 60_000,
  });
  const features: Features = query.data?.features ?? {};
  return {
    isLoading: query.isLoading,
    enabled: (name: string) => features[name] === true,
  };
}
