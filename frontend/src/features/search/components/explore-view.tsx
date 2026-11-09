"use client";

import { Compass, Star } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { useQuery } from "@/lib/api/use-query";

import { toQuery, useDataset } from "../api";
import { addDays, formatDay, formatMoney, todayIso } from "../format";
import { LocationPicker, type PickedLocation } from "./location-picker";

type Filters = { origin: PickedLocation; date: string; nights: number; adults: number; budget: string };

/** "Where can this budget take me?": flight and stay totals for every city in the data. */
export function ExploreView() {
  const dataset = useDataset();
  const [origin, setOrigin] = useState<PickedLocation | null>({ value: "DEL", label: "Delhi" });
  const [date, setDate] = useState("");
  const [nights, setNights] = useState(3);
  const [adults, setAdults] = useState(2);
  const [budget, setBudget] = useState("");
  const [applied, setApplied] = useState<Filters | null>(null);

  const first = dataset.data?.travel_window?.first_departure;
  const soonest = addDays(todayIso(), 21);
  const defaultDate = first && first > soonest ? first : soonest;
  const shownDate = date || defaultDate;
  const filters = applied ?? (origin ? { origin, date: shownDate, nights, adults, budget } : null);
  const ready = Boolean(filters && (applied || dataset.data));

  const { data, error, isFetching } = useQuery({
    queryKey: ["explore", filters?.origin.value, filters?.date, filters?.nights, filters?.adults, filters?.budget],
    queryFn: () =>
      apiFetch<Schemas["ExploreOut"]>(
        `/explore?${toQuery({
          origin: filters!.origin.value,
          departure_date: filters!.date,
          nights: filters!.nights,
          adults: filters!.adults,
          budget: filters!.budget ? Number(filters!.budget) : undefined,
        })}`,
      ),
    enabled: ready,
    retry: false,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (origin) setApplied({ origin, date: shownDate, nights, adults, budget });
  }

  return (
    <div className="grid gap-6">
      <Card className="tm-overlap p-4">
        <form onSubmit={submit} className="grid grid-cols-[minmax(0,1fr)] items-end gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_auto]">
          <div className="grid gap-1.5">
            <Label htmlFor="explore-from">Leaving from</Label>
            <LocationPicker id="explore-from" kind="airport" value={origin} onChange={setOrigin} placeholder="City or airport" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="explore-date">Leave on</Label>
            <Input id="explore-date" type="date" min={todayIso()} value={shownDate} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="explore-nights">Nights</Label>
            <Select value={String(nights)} onValueChange={(value) => setNights(Number(value))}>
              <SelectTrigger id="explore-nights" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[2, 3, 4, 5, 7, 10].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} nights
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="explore-adults">Travellers</Label>
            <Select value={String(adults)} onValueChange={(value) => setAdults(Number(value))}>
              <SelectTrigger id="explore-adults" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n} adult{n > 1 ? "s" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="explore-budget">Budget in ₹</Label>
            <Input id="explore-budget" inputMode="numeric" placeholder="Any" value={budget} onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))} />
          </div>
          <Button type="submit" size="lg" disabled={isFetching || !origin}>
            <Compass /> Explore
          </Button>
        </form>
      </Card>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}
      {isFetching && !data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      ) : null}
      {data ? (
        <section className="grid gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2>
              {data.options.length} place{data.options.length === 1 ? "" : "s"} from {filters?.origin.label}
            </h2>
            <p className="text-sm text-muted-foreground">
              {formatDay(data.departure_date)} to {formatDay(data.return_date)} · {data.nights} nights · {data.adults} adult{data.adults > 1 ? "s" : ""}
              {data.over_budget ? ` · ${data.over_budget} over budget hidden` : ""}
            </p>
          </div>
          {data.options.length === 0 ? <p className="py-6 text-center text-muted-foreground">Nothing fits. Try a higher budget or other dates.</p> : null}
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.options.map((option) => (
              <li key={option.city_id}>
                <Card className="grid h-full gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="tm-explore-city">{option.city}</h3>
                    <span className="text-xs text-muted-foreground">{option.airport_code}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {option.stay_option.name}
                    {option.stay_option.guest_rating ? (
                      <span className="ml-1 inline-flex items-center gap-0.5">
                        <Star className="size-3 fill-current" aria-hidden /> {option.stay_option.guest_rating}
                      </span>
                    ) : null}
                  </p>
                  <dl className="grid grid-cols-2 gap-x-3 text-sm">
                    <dt className="text-muted-foreground">Flights</dt>
                    <dd className="text-right tabular-nums">{formatMoney(option.flights)}</dd>
                    <dt className="text-muted-foreground">Stay</dt>
                    <dd className="text-right tabular-nums">{formatMoney(option.stay)}</dd>
                    <dt className="font-semibold">Total</dt>
                    <dd className="text-right font-semibold tabular-nums">{formatMoney(option.total)}</dd>
                  </dl>
                  <Button asChild variant="outline" size="sm" className="mt-auto">
                    <Link
                      href={`/plan?${toQuery({
                        origin: data.origin,
                        originLabel: filters?.origin.label,
                        dest: option.city_id,
                        destLabel: option.city,
                        depart: data.departure_date,
                        return: data.return_date,
                        adults: data.adults,
                      })}`}
                    >
                      Plan this trip
                    </Link>
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">{data.note}</p>
        </section>
      ) : null}
    </div>
  );
}
