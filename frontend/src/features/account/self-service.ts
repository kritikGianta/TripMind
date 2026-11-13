"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useSession } from "@/features/auth/hooks";
import { toQuery } from "@/features/search/api";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { useQuery } from "@/lib/api/use-query";

export type SavedHotel = Schemas["SavedHotelOut"];
export type PriceAlert = Schemas["PriceAlertOut"];
export type RecentSearch = Schemas["SearchHistoryOut"];
export type MyReview = Schemas["MyReviewOut"];
export type AwaitingReview = Schemas["AwaitingReviewOut"];
export type Watch = Schemas["PriceAlertIn"]["watch"];

/** Lists that only exist for a signed-in traveller stay idle until there is one. */
function useSignedIn() {
  return useSession().status === "authenticated";
}

export function useSavedHotels() {
  const enabled = useSignedIn();
  return useQuery({
    queryKey: ["me", "saved-hotels"],
    queryFn: () => apiFetch<Schemas["SavedHotelListOut"]>("/me/saved-hotels"),
    enabled,
  });
}

export function useToggleSaved() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ hotelId, saved }: { hotelId: string; saved: boolean }) =>
      apiFetch<Schemas["SavedHotelListOut"]>(`/me/saved-hotels/${hotelId}`, { method: saved ? "DELETE" : "PUT" }),
    onSuccess: (list) => client.setQueryData(["me", "saved-hotels"], list),
  });
}

export function usePriceAlerts() {
  const enabled = useSignedIn();
  return useQuery({
    queryKey: ["me", "price-alerts"],
    queryFn: () => apiFetch<Schemas["PriceAlertListOut"]>("/me/price-alerts"),
    enabled,
  });
}

export function useCreateAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { watch: Watch; target_price?: number | null }) =>
      apiFetch<PriceAlert>("/me/price-alerts", { method: "POST", body }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "price-alerts"] }),
  });
}

export function useDeleteAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/me/price-alerts/${id}`, { method: "DELETE" }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "price-alerts"] }),
  });
}

export function useRecentSearches() {
  const enabled = useSignedIn();
  return useQuery({
    queryKey: ["me", "searches"],
    queryFn: () => apiFetch<Schemas["SearchHistoryListOut"]>("/me/searches"),
    enabled,
  });
}

export function useForgetSearch() {
  const client = useQueryClient();
  return useMutation({
    /** With no id, clears the whole history. */
    mutationFn: (id: string | null) => apiFetch<void>(id ? `/me/searches/${id}` : "/me/searches", { method: "DELETE" }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "searches"] }),
  });
}

/** Rebuilds the link a recent search came from, so it can be run again in one click. */
export function searchLink(search: RecentSearch): string {
  const p = search.params as Record<string, string | number | null | undefined>;
  // The history keeps ids; the names come from its label, such as "Delhi → Goa · 12 Nov".
  const names = search.label.split(" · ")[0];
  if (search.vertical === "flights") {
    const [fromName, toName] = names.split(" → ");
    return `/flights?${toQuery({
      from: p.origin as string,
      fromLabel: fromName ?? (p.origin as string),
      to: p.destination as string,
      toLabel: toName ?? (p.destination as string),
      depart: p.departure_date as string,
      return: p.return_date as string,
      adults: p.adults as number,
      cabin: p.cabin_class as string,
    })}`;
  }
  return `/stays?${toQuery({
    city: p.city as string,
    cityName: names.replace(/^Stays in /, ""),
    checkIn: p.check_in as string,
    checkOut: p.check_out as string,
    guests: p.guests as number,
    rooms: p.rooms as number,
  })}`;
}

export function useMyReviews() {
  const enabled = useSignedIn();
  return useQuery({
    queryKey: ["me", "reviews"],
    queryFn: () => apiFetch<Schemas["MyReviewsOut"]>("/me/reviews"),
    enabled,
  });
}

export function useDeleteReview() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/me/reviews/${id}`, { method: "DELETE" }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "reviews"] }),
  });
}

export function useWriteReview(bookingId: string, itemId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["ReviewIn"]) =>
      apiFetch<MyReview>(`/bookings/${bookingId}/items/${itemId}/review`, { method: "POST", body }),
    onSettled: () => void client.invalidateQueries({ queryKey: ["me", "reviews"] }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: Schemas["PasswordChange"]) =>
      apiFetch<Schemas["SessionOut"]>("/auth/password", { method: "POST", body }),
  });
}

export function useSignOutEverywhere() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>("/auth/logout-all", { method: "POST" }),
    onSuccess: () => client.clear(),
  });
}

export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => apiFetch<void>("/me", { method: "DELETE", body: { password } }),
    onSuccess: () => client.clear(),
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) =>
      apiFetch<Schemas["PasswordForgotOut"]>("/auth/password/forgot", { method: "POST", body: { email } }),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (body: Schemas["PasswordReset"]) =>
      apiFetch<void>("/auth/password/reset", { method: "POST", body }),
  });
}

/** Downloads everything held about the traveller as one JSON file. */
export async function downloadMyData() {
  const data = await apiFetch<Record<string, unknown>>("/me/export");
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "tripmind-my-data.json";
  link.click();
  URL.revokeObjectURL(url);
}
