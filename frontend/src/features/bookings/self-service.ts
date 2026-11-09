"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type Schemas } from "@/lib/api/client";
import { useQuery } from "@/lib/api/use-query";

import type { Booking } from "./api";

export type ChangeQuote = Schemas["ChangeQuoteOut"];
export type ChangeRequest = Schemas["ChangeRequest"];
export type ExtrasCatalog = Schemas["ExtrasCatalogOut"];
export type ExtrasQuote = Schemas["ExtrasQuoteOut"];
export type Selection = Schemas["Selection"];
export type SeatMap = Schemas["SeatMapOut"];
export type PaymentInput = Schemas["PaymentRequest"];

export function useChangeQuote(bookingId: string, itemId: string) {
  return useMutation({
    mutationFn: (body: ChangeRequest) =>
      apiFetch<ChangeQuote>(`/bookings/${bookingId}/items/${itemId}/change-quote`, { method: "POST", body }),
  });
}

export function useConfirmChange(bookingId: string, itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ChangeConfirm"]) =>
      // A fresh key per attempt: a retry after a decline is a new payment, a double-click is not.
      apiFetch<Booking>(`/bookings/${bookingId}/items/${itemId}/change`, {
        method: "POST",
        body,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: (booking) => client.setQueryData(["booking", bookingId], booking),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["booking", bookingId] });
      void client.invalidateQueries({ queryKey: ["trips"] });
    },
  });
}

export function useExtrasCatalog(bookingId: string, itemId: string) {
  return useQuery({
    queryKey: ["extras", bookingId, itemId],
    queryFn: () => apiFetch<ExtrasCatalog>(`/bookings/${bookingId}/items/${itemId}/extras`),
  });
}

export function useSeatMap(bookingId: string, itemId: string, flightId: string | null) {
  return useQuery({
    queryKey: ["seat-map", bookingId, itemId, flightId],
    queryFn: () => apiFetch<SeatMap>(`/bookings/${bookingId}/items/${itemId}/seat-map?flight_id=${flightId}`),
    enabled: flightId !== null,
  });
}

export function useExtrasQuote(bookingId: string, itemId: string, selections: Selection[]) {
  return useQuery({
    queryKey: ["extras-quote", bookingId, itemId, selections],
    queryFn: () =>
      apiFetch<ExtrasQuote>(`/bookings/${bookingId}/items/${itemId}/extras/quote`, { method: "POST", body: { selections } }),
    placeholderData: (previous) => previous,
    retry: false,
  });
}

export function usePurchaseExtras(bookingId: string, itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ExtrasPurchase"]) =>
      apiFetch<Booking>(`/bookings/${bookingId}/items/${itemId}/extras`, {
        method: "POST",
        body,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    onSuccess: (booking) => client.setQueryData(["booking", bookingId], booking),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["extras", bookingId, itemId] });
      void client.invalidateQueries({ queryKey: ["seat-map", bookingId, itemId] });
    },
  });
}

export function useTripSuggestions(tripId: string) {
  return useQuery({
    queryKey: ["trip-suggestions", tripId],
    queryFn: () => apiFetch<Schemas["TripSuggestionsOut"]>(`/trips/${tripId}/suggestions`),
    retry: false,
  });
}
