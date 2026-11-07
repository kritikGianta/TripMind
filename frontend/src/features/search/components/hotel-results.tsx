"use client";

import { AlertCircle, MapPin, SlidersHorizontal, Star } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { toQuery, useHotelSearch, type HotelResult, type HotelSearch } from "../api";
import { BOARD_LABELS, formatDay } from "../format";
import { CheckboxFacet, FilterGroup, PriceFacet, SortBar, useUrlState } from "./filters";
import { PriceBreakdown } from "./price-breakdown";
import { SearchPanel } from "./search-panel";

const SORTS = [
  { value: "recommended", label: "Recommended" },
  { value: "price", label: "Lowest price" },
  { value: "rating", label: "Top rated" },
  { value: "distance", label: "Closest" },
] as const;
type Sort = (typeof SORTS)[number]["value"];

export function Stars({ count }: { count: number | null | undefined }) {
  if (!count) return null;
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-500" aria-label={`${count} star`}>
      {Array.from({ length: Math.round(count) }, (_, i) => (
        <Star key={i} className="size-3.5 fill-current" aria-hidden />
      ))}
    </span>
  );
}

export function RatingBadge({ rating, reviews }: { rating: number | null | undefined; reviews?: number | null }) {
  if (rating === null || rating === undefined) return null;
  const word = rating >= 9 ? "Exceptional" : rating >= 8 ? "Very good" : rating >= 7 ? "Good" : "Rated";
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span className="rounded-md bg-primary px-1.5 py-0.5 font-semibold text-primary-foreground tabular-nums">
        {rating.toFixed(1)}
      </span>
      <span>
        {word}
        {reviews ? <span className="text-muted-foreground"> · {reviews.toLocaleString("en-IN")} reviews</span> : null}
      </span>
    </span>
  );
}

function HotelCard({ hotel, search, stayQuery }: { hotel: HotelResult; search: HotelSearch; stayQuery: string }) {
  const room = hotel.cheapest_room;
  return (
    <Card className="grid gap-4 p-4 md:grid-cols-[1fr_auto]">
      <div className="grid content-start gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/stays/${hotel.id}?${stayQuery}`} className="text-lg font-semibold hover:underline">
            {hotel.name}
          </Link>
          <Stars count={hotel.star_rating} />
        </div>
        <p className="flex items-center gap-1 text-sm text-muted-foreground">
          <MapPin className="size-3.5" aria-hidden />
          {hotel.city_name}
          {hotel.distance_km !== null && hotel.distance_km !== undefined ? ` · ${hotel.distance_km} km from centre` : ""}
        </p>
        <RatingBadge rating={hotel.guest_rating} reviews={hotel.review_count} />
        <div className="text-sm">
          <span className="font-medium">{room.name}</span>
          <span className="text-muted-foreground"> · sleeps {room.max_occupancy}{room.bed_type ? ` · ${room.bed_type}` : ""}</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {room.refundable ? <Badge variant="outline" className="text-emerald-700 dark:text-emerald-400">Free cancellation</Badge> : null}
          {room.board ? <Badge variant="outline">{BOARD_LABELS[room.board] ?? room.board}</Badge> : null}
          {room.origin === "derived" ? <Badge variant="outline">Room details not in data</Badge> : null}
        </div>
      </div>
      <div className="grid content-between justify-items-end gap-3">
        {room.price ? (
          <PriceBreakdown
            ledger={room.price}
            caption={`${search.nights} night${search.nights > 1 ? "s" : ""}, ${search.rooms} room${search.rooms > 1 ? "s" : ""}`}
          />
        ) : null}
        <Button asChild>
          <Link href={`/stays/${hotel.id}?${stayQuery}`}>{hotel.bookable ? "See rooms" : "View details"}</Link>
        </Button>
      </div>
    </Card>
  );
}

function Filters({ search }: { search: HotelSearch }) {
  const { params, update } = useUrlState();
  return (
    <div className="grid gap-4">
      <FilterGroup title="Your budget (per night)">
        <PriceFacet
          range={search.facets.price_range}
          value={params.get("maxPrice") ? Number(params.get("maxPrice")) : null}
          onCommit={(max) => update({ maxPrice: max === null ? null : String(max) })}
          caption="Per night"
        />
      </FilterGroup>
      <FilterGroup title="Popular">
        {[
          { key: "freeCancellation", label: "Free cancellation" },
          { key: "breakfast", label: "Breakfast included" },
        ].map(({ key, label }) => (
          <div key={key} className="flex items-center gap-2 text-sm">
            <Checkbox
              id={key}
              checked={params.get(key) === "true"}
              onCheckedChange={(state) => update({ [key]: state ? "true" : null })}
            />
            <Label htmlFor={key} className="font-normal">
              {label}
            </Label>
          </div>
        ))}
      </FilterGroup>
      <FilterGroup title="Star rating">
        <CheckboxFacet name="stars" options={search.facets.stars} selected={params.getAll("stars")} onChange={(v) => update({ stars: v })} />
      </FilterGroup>
      <FilterGroup title="Guest rating">
        <CheckboxFacet
          name="rating"
          options={[
            { value: "9", label: "Exceptional 9+", count: search.results.filter((r) => (r.guest_rating ?? 0) >= 9).length },
            { value: "8", label: "Very good 8+", count: search.results.filter((r) => (r.guest_rating ?? 0) >= 8).length },
            { value: "7", label: "Good 7+", count: search.results.filter((r) => (r.guest_rating ?? 0) >= 7).length },
          ]}
          selected={params.get("minRating") ? [params.get("minRating")!] : []}
          onChange={(v) => update({ minRating: v.at(-1) ?? null })}
        />
      </FilterGroup>
      <FilterGroup title="Facilities">
        <CheckboxFacet
          name="amenity"
          options={search.facets.amenities}
          selected={params.getAll("amenity")}
          onChange={(v) => update({ amenity: v })}
        />
      </FilterGroup>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => update({ stars: [], amenity: [], maxPrice: null, minRating: null, freeCancellation: null, breakfast: null })}
      >
        Clear filters
      </Button>
    </div>
  );
}

export function HotelResultsView() {
  const { params, update } = useUrlState();
  const city = params.get("city");
  const checkIn = params.get("checkIn");
  const checkOut = params.get("checkOut");
  const guests = Number(params.get("guests") ?? 2);
  const rooms = Number(params.get("rooms") ?? 1);
  const sort = (params.get("sort") ?? "recommended") as Sort;

  const query = useMemo(() => {
    if (!city || !checkIn || !checkOut) return null;
    return toQuery({
      city,
      check_in: checkIn,
      check_out: checkOut,
      guests,
      rooms,
      stars: params.getAll("stars"),
      amenities: params.getAll("amenity"),
      min_rating: params.get("minRating") ?? undefined,
      max_price: params.get("maxPrice") ?? undefined,
      free_cancellation: params.get("freeCancellation") === "true",
      breakfast: params.get("breakfast") === "true",
      sort,
    });
  }, [city, checkIn, checkOut, guests, rooms, sort, params]);

  const stayQuery = toQuery({ checkIn, checkOut, guests, rooms, trip: params.get("trip") });
  const { data, error, isPending, isFetching } = useHotelSearch(query);

  const panel = (
    <SearchPanel
      defaultTab="stays"
      stay={{
        city: city ? { value: city, label: params.get("cityName") ?? "Selected city" } : null,
        checkIn: checkIn ?? "",
        checkOut: checkOut ?? "",
        guests,
        rooms,
      }}
    />
  );
  if (!query) return <div className="mx-auto w-full max-w-6xl px-4 py-8">{panel}</div>;

  const filters = data ? <Filters search={data} /> : null;

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-6">
      {panel}
      {error ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{errorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}
      {data?.notices.map((n) => (
        <Alert key={n}>
          <AlertCircle />
          <AlertDescription>{n}</AlertDescription>
        </Alert>
      ))}
      <div className="grid gap-6 md:grid-cols-[15rem_1fr]">
        <aside className="hidden md:block">{filters}</aside>
        <section aria-busy={isFetching} className="grid content-start gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold">{data ? `Stays in ${data.city.name}` : "Stays"}</h1>
              {data ? (
                <p className="text-sm text-muted-foreground">
                  {formatDay(data.check_in)} – {formatDay(data.check_out)} · {data.nights} night{data.nights > 1 ? "s" : ""} ·{" "}
                  {data.guests} guest{data.guests > 1 ? "s" : ""} · {data.total} of {data.unfiltered_total} properties
                  {sort === "recommended"
                    ? data.ranked_by.startsWith("model:")
                      ? ` · ordered by TripMind's ranking model (${data.ranked_by.slice(6)})`
                      : " · ordered by rating, value and stars"
                    : ""}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm" className="md:hidden">
                    <SlidersHorizontal /> Filters
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="overflow-y-auto">
                  <SheetHeader>
                    <SheetTitle>Filters</SheetTitle>
                  </SheetHeader>
                  <div className="px-4">{filters}</div>
                </SheetContent>
              </Sheet>
              <SortBar options={[...SORTS]} value={sort} onChange={(v) => update({ sort: v })} />
            </div>
          </div>
          {isPending ? (
            Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-40 w-full" />)
          ) : data && data.results.length ? (
            data.results.map((hotel) => <HotelCard key={hotel.id} hotel={hotel} search={data} stayQuery={stayQuery} />)
          ) : data ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">
              {data.unfiltered_total
                ? "No stays match these filters. Try clearing some of them."
                : "No stays in this city fit your party size in the dataset."}
            </Card>
          ) : null}
        </section>
      </div>
    </div>
  );
}
