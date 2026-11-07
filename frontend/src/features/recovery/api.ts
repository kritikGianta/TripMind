"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

export type RecoveryCase = Schemas["RecoveryCaseOut"];
export type RecoveryOption = Schemas["RecoveryOptionOut"];
export type Notification = Schemas["NotificationOut"];

export function useNotifications(enabled: boolean) {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => apiFetch<Schemas["NotificationListOut"]>("/notifications"),
    enabled,
    refetchInterval: 30_000, // simple polling; a push channel is not needed for the demo
  });
}

export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id?: string) => apiFetch<void>(`/notifications/read${id ? `?notification_id=${id}` : ""}`, { method: "POST" }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useBookingCases(bookingId: string) {
  return useQuery({
    queryKey: ["recovery", "booking", bookingId],
    queryFn: () => apiFetch<Schemas["RecoveryCaseListOut"]>(`/recovery/cases?booking_id=${bookingId}`),
  });
}

export function useCase(id: string) {
  return useQuery({ queryKey: ["recovery", id], queryFn: () => apiFetch<RecoveryCase>(`/recovery/cases/${id}`) });
}

export function useAccept(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (optionId: string) =>
      apiFetch<RecoveryCase>(`/recovery/cases/${caseId}/accept`, { method: "POST", body: { option_id: optionId } }),
    onSuccess: (c) => client.setQueryData(["recovery", caseId], c),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["booking"] });
      void client.invalidateQueries({ queryKey: ["recovery"] });
      void client.invalidateQueries({ queryKey: ["notifications"] });
      void client.invalidateQueries({ queryKey: ["trips"] });
    },
  });
}

export function useBookedFlights() {
  return useQuery({
    queryKey: ["admin", "booked-flights"],
    queryFn: () => apiFetch<Schemas["BookedFlightListOut"]>("/admin/operations/booked-flights"),
  });
}

export function useDisruptions() {
  return useQuery({
    queryKey: ["admin", "disruptions"],
    queryFn: () => apiFetch<Schemas["DisruptionListOut"]>("/admin/operations/disruptions"),
  });
}

export function useDisrupt() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["DisruptionIn"]) =>
      apiFetch<Schemas["DisruptionOut"]>("/admin/operations/disruptions", { method: "POST", body }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["admin"] }),
  });
}
