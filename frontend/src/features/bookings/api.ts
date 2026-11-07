"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

export type Booking = Schemas["BookingOut"];
export type BookingItem = Schemas["BookingItemOut"];
export type Quote = Schemas["QuoteOut"];
export type ItemIn = Schemas["QuoteRequest"]["items"][number];
export type CreateBooking = Schemas["CreateBookingRequest"];
export type PaymentInput = Schemas["PaymentRequest"];
export type Trip = Schemas["TripOut"];
export type CancellationQuote = Schemas["CancellationQuoteOut"];

export function useQuote(items: ItemIn[] | null, promoCode: string | null = null) {
  return useQuery({
    queryKey: ["quote", items, promoCode],
    queryFn: () => apiFetch<Quote>("/bookings/quote", { method: "POST", body: { items, promo_code: promoCode } }),
    enabled: items !== null && items.length > 0,
    staleTime: 60_000,
  });
}

export function useBooking(id: string) {
  return useQuery({
    queryKey: ["booking", id],
    queryFn: () => apiFetch<Booking>(`/bookings/${id}`),
  });
}

export function useTrips() {
  return useQuery({ queryKey: ["trips"], queryFn: () => apiFetch<Schemas["TripListOut"]>("/trips") });
}

export function useTrip(id: string) {
  return useQuery({ queryKey: ["trip", id], queryFn: () => apiFetch<Trip>(`/trips/${id}`) });
}

export function useCreateBooking(idempotencyKey: string) {
  return useMutation({
    mutationFn: (body: CreateBooking) =>
      apiFetch<Booking>("/bookings", { method: "POST", body, headers: { "Idempotency-Key": idempotencyKey } }),
  });
}

export function usePay(bookingId: string) {
  const client = useQueryClient();
  return useMutation({
    // A fresh key per attempt: a retry after a decline is a new payment, a double-click is not.
    mutationFn: ({ input, key }: { input: PaymentInput; key: string }) =>
      apiFetch<Booking>(`/bookings/${bookingId}/payments`, {
        method: "POST",
        body: input,
        headers: { "Idempotency-Key": key },
      }),
    onSuccess: (booking) => client.setQueryData(["booking", bookingId], booking),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["booking", bookingId] });
      void client.invalidateQueries({ queryKey: ["trips"] });
    },
  });
}

export function useCancellationQuote(bookingId: string, itemIds: string[] | null) {
  const query = new URLSearchParams();
  (itemIds ?? []).forEach((id) => query.append("item_id", id));
  return useQuery({
    queryKey: ["cancellation", bookingId, itemIds],
    queryFn: () => apiFetch<CancellationQuote>(`/bookings/${bookingId}/cancellation?${query}`),
    enabled: itemIds !== null,
  });
}

export function useCancel(bookingId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (itemIds: string[] | null) =>
      apiFetch<Booking>(`/bookings/${bookingId}/cancel`, {
        method: "POST",
        body: { item_ids: itemIds && itemIds.length ? itemIds : null },
      }),
    onSuccess: (booking) => client.setQueryData(["booking", bookingId], booking),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["trips"] });
      void client.invalidateQueries({ queryKey: ["trip"] });
    },
  });
}
