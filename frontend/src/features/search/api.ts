"use client";

import { keepPreviousData } from "@tanstack/react-query";
import { useQuery } from "@/lib/api/use-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

export type LocationKind = "airport" | "city";
export type Location = Schemas["LocationOut"];
export type FlightSearch = Schemas["FlightSearchOut"];
export type FlightOffer = Schemas["FlightOfferOut"];
export type FlightResults = Schemas["FlightResultsOut"];
export type HotelSearch = Schemas["HotelSearchOut"];
export type HotelResult = Schemas["HotelResultOut"];
export type HotelDetail = Schemas["HotelDetailOut"];
export type RoomOffer = Schemas["RoomOfferOut"];
export type PriceLedger = Schemas["PriceLedger"];
export type DatasetSummary = Schemas["DatasetSummaryOut"];

/** Build a query string; arrays become repeated keys (?stars=4&stars=5), empty values are dropped. */
export function toQuery(params: Record<string, string | number | boolean | string[] | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "" || value === false) continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else search.set(key, String(value));
  }
  return search.toString();
}

export function useLocations(q: string, kind: LocationKind) {
  return useQuery({
    queryKey: ["locations", kind, q],
    queryFn: ({ signal }) =>
      apiFetch<Schemas["LocationListOut"]>(`/locations?${toQuery({ q, kind, limit: 8 })}`, { signal }),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
}

export function useDataset() {
  return useQuery({
    queryKey: ["datasets", "current"],
    queryFn: () => apiFetch<DatasetSummary>("/datasets/current"),
    staleTime: 5 * 60_000,
  });
}

export function useFlightSearch(query: string | null) {
  return useQuery({
    queryKey: ["flights", query],
    queryFn: ({ signal }) => apiFetch<FlightSearch>(`/flights/search?${query}`, { signal }),
    enabled: query !== null,
    placeholderData: keepPreviousData,
  });
}

export function useHotelSearch(query: string | null) {
  return useQuery({
    queryKey: ["hotels", query],
    queryFn: ({ signal }) => apiFetch<HotelSearch>(`/hotels/search?${query}`, { signal }),
    enabled: query !== null,
    placeholderData: keepPreviousData,
  });
}

export function useHotel(id: string, query: string) {
  return useQuery({
    queryKey: ["hotel", id, query],
    queryFn: ({ signal }) => apiFetch<HotelDetail>(`/hotels/${id}?${query}`, { signal }),
  });
}
