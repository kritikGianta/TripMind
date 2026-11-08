"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/api/use-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

export type SavedTraveller = Schemas["TravellerProfileOut"];

export function useSavedTravellers(enabled = true) {
  return useQuery({
    queryKey: ["me", "travellers"],
    queryFn: () => apiFetch<Schemas["TravellerProfileListOut"]>("/me/travellers"),
    enabled,
  });
}

export function useAddTraveller() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["TravellerProfileIn"]) =>
      apiFetch<SavedTraveller>("/me/travellers", { method: "POST", body }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "travellers"] }),
  });
}

export function useDeleteTraveller() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/me/travellers/${id}`, { method: "DELETE" }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "travellers"] }),
  });
}

export function useLoyalty() {
  return useQuery({ queryKey: ["me", "loyalty"], queryFn: () => apiFetch<Schemas["LoyaltyOut"]>("/me/loyalty") });
}
