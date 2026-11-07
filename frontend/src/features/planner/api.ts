"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

export type Plan = Schemas["PlanOut"];
export type Bundle = Schemas["BundleOut"];
export type PlanRequest = Schemas["PlanRequest"];
export type OptionState = Schemas["OptionStateIn"]["state"];

export function usePlan(id: string) {
  return useQuery({ queryKey: ["plan", id], queryFn: () => apiFetch<Plan>(`/plans/${id}`) });
}

export function usePlans() {
  return useQuery({ queryKey: ["plans"], queryFn: () => apiFetch<Schemas["PlanListOut"]>("/plans") });
}

export function useCreatePlan() {
  return useMutation({
    mutationFn: (body: PlanRequest) => apiFetch<Plan>("/plans", { method: "POST", body }),
  });
}

export function useOptionState(planId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ optionId, state }: { optionId: string; state: OptionState }) =>
      apiFetch<Plan>(`/plans/${planId}/options/${optionId}`, { method: "PUT", body: { state } }),
    onSuccess: (plan) => {
      client.setQueryData(["plan", planId], plan);
      void client.invalidateQueries({ queryKey: ["plans"] });
    },
  });
}
