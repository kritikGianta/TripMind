"use client";

import { BellRing, Bookmark, BookmarkCheck, MessageSquareQuote, Star } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { searchLink, useCreateAlert, useRecentSearches, useSavedHotels, useToggleSaved, type Watch } from "@/features/account/self-service";
import { useSession } from "@/features/auth/hooks";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { useQuery } from "@/lib/api/use-query";

import { addDays, formatDay, formatMoney, todayIso } from "../format";
import { toQuery } from "../api";

/** Sends someone signed out to sign in, and back here afterwards. */
function useSignInLink() {
  const path = usePathname();
  const params = useSearchParams().toString();
  return `/sign-in?next=${encodeURIComponent(params ? `${path}?${params}` : path)}`;
}

export function SaveStayButton({ hotelId }: { hotelId: string }) {
  const { status } = useSession();
  const signIn = useSignInLink();
  const saved = useSavedHotels();
  const toggle = useToggleSaved();
  const isSaved = saved.data?.items.some((item) => item.hotel_id === hotelId) ?? false;
  if (status === "unauthenticated") {
    return (
      <Button asChild variant="outline" size="sm">
        <Link href={signIn}>
          <Bookmark /> Save
        </Link>
      </Button>
    );
  }
  return (
    <Button
      variant="outline"
      size="sm"
      aria-pressed={isSaved}
      disabled={toggle.isPending || status === "loading"}
      onClick={() =>
        toggle.mutate(
          { hotelId, saved: isSaved },
          {
            onSuccess: () => toast.success(isSaved ? "Removed from saved stays." : "Saved. Find it in your account."),
            onError: (error) => toast.error(errorMessage(error)),
          },
        )
      }
    >
      {isSaved ? <BookmarkCheck /> : <Bookmark />} {isSaved ? "Saved" : "Save"}
    </Button>
  );
}

/** Watches the price of a flight search or a stay. Needs prices to watch, so it waits for dates. */
export function WatchPriceButton({ watch, label = "Watch price" }: { watch: Watch; label?: string }) {
  const { status } = useSession();
  const signIn = useSignInLink();
  const create = useCreateAlert();
  const [done, setDone] = useState(false);
  if (status === "unauthenticated") {
    return (
      <Button asChild variant="outline" size="sm">
        <Link href={signIn}>
          <BellRing /> {label}
        </Link>
      </Button>
    );
  }
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={create.isPending || done || status === "loading"}
      onClick={() =>
        create.mutate(
          { watch },
          {
            onSuccess: () => {
              setDone(true);
              toast.success("We'll tell you if the price drops.");
            },
            onError: (error) => toast.error(errorMessage(error)),
          },
        )
      }
    >
      <BellRing /> {done ? "Watching" : label}
    </Button>
  );
}

export function HotelReviews({ hotelId }: { hotelId: string }) {
  const [sort, setSort] = useState<"recent" | "highest" | "lowest">("recent");
  const [limit, setLimit] = useState(5);
  const { data, isPending } = useQuery({
    queryKey: ["hotel-reviews", hotelId, sort, limit],
    queryFn: () => apiFetch<Schemas["HotelReviewsOut"]>(`/hotels/${hotelId}/reviews?${toQuery({ sort, limit })}`),
  });

  if (isPending) return <Skeleton className="h-40 w-full" />;
  if (!data || data.summary.total === 0) {
    return (
      <Card className="grid gap-2 p-5">
        <h2>Guest reviews</h2>
        <p className="text-sm text-muted-foreground">No reviews yet. Guests can write one after they check out.</p>
      </Card>
    );
  }
  const { summary } = data;
  return (
    <Card className="grid gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2">
          <MessageSquareQuote className="size-4" aria-hidden /> Guest reviews
        </h2>
        <Select value={sort} onValueChange={(value) => setSort(value as typeof sort)}>
          <SelectTrigger aria-label="Sort reviews" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="recent">Most recent</SelectItem>
            <SelectItem value="highest">Highest rated</SelectItem>
            <SelectItem value="lowest">Lowest rated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-3 md:grid-cols-[14rem_1fr]">
        <div>
          {summary.average_rating !== null ? <p className="tm-serif-score">{summary.average_rating.toFixed(1)}/10</p> : null}
          <p className="text-sm text-muted-foreground">
            {summary.total} review{summary.total === 1 ? "" : "s"}
          </p>
          {summary.note ? <p className="mt-1 text-xs text-muted-foreground">{summary.note}</p> : null}
        </div>
      </div>

      <ul className="grid gap-3">
        {data.items.map((review) => (
          <li key={review.id} className="grid gap-1 border-t pt-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {review.rating !== null ? (
                <span className="flex items-center gap-1 font-medium">
                  <Star className="size-3.5 fill-current" aria-hidden /> {review.rating}
                </span>
              ) : null}
              {review.title ? <span className="font-medium">{review.title}</span> : null}
              {review.verified_stay ? <Badge variant="secondary">Verified stay</Badge> : null}
            </div>
            <p className="text-sm text-muted-foreground">{review.text}</p>
            <p className="text-xs text-muted-foreground">
              {review.traveller_type ? `${review.traveller_type} · ` : ""}
              {review.date ? formatDay(review.date) : ""}
            </p>
          </li>
        ))}
      </ul>
      {summary.total > data.items.length ? (
        <Button variant="outline" size="sm" className="w-fit" onClick={() => setLimit(limit + 10)}>
          Show more
        </Button>
      ) : null}
    </Card>
  );
}

/** The cheapest fare per day around the chosen date. Clicking a day searches that day. */
export function FareCalendar({
  origin,
  destination,
  date,
  adults,
  cabin,
  onPick,
}: {
  origin: string;
  destination: string;
  date: string;
  adults: number;
  cabin: string;
  onPick: (date: string) => void;
}) {
  const today = todayIso();
  const start = addDays(date, -3) < today ? today : addDays(date, -3);
  const { data, isPending } = useQuery({
    queryKey: ["fare-calendar", origin, destination, start, adults, cabin],
    queryFn: () =>
      apiFetch<Schemas["FareCalendarOut"]>(`/flights/calendar?${toQuery({ origin, destination, start, days: 14, adults, cabin_class: cabin })}`),
    staleTime: 5 * 60_000,
    retry: false,
  });
  if (isPending) return <Skeleton className="h-20 w-full" />;
  if (!data || data.days.every((d) => !d.cheapest)) return null;
  return (
    <section aria-label="Fare calendar" className="grid gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2>Cheapest days to fly</h2>
        <p className="text-xs text-muted-foreground">{data.note}</p>
      </div>
      <ol className="tm-fare-days">
        {data.days.map((day) => (
          <li key={day.date}>
            <button
              type="button"
              className="tm-fare-day"
              data-level={day.level ?? undefined}
              aria-current={day.date === date ? "date" : undefined}
              disabled={!day.cheapest}
              onClick={() => onPick(day.date)}
            >
              <span className="text-xs">{formatDay(day.date)}</span>
              <span className="font-medium tabular-nums">{day.cheapest ? formatMoney(day.cheapest) : "—"}</span>
              {day.date === data.cheapest_day ? <span className="text-[0.65rem] uppercase">Cheapest</span> : null}
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** A signed-in traveller's last searches, one click from running again. */
export function RecentSearchChips({ vertical }: { vertical: "flights" | "hotels" }) {
  const { data } = useRecentSearches();
  const items = data?.items.filter((item) => item.vertical === vertical).slice(0, 4) ?? [];
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="text-muted-foreground">Pick up where you left off:</span>
      {items.map((item) => (
        <Button key={item.id} asChild variant="outline" size="sm">
          <Link href={searchLink(item)}>{item.label}</Link>
        </Button>
      ))}
    </div>
  );
}
