"use client";

import { ChevronDown, Plane } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { FlightOffer } from "../api";
import { CABIN_LABELS, clockTime, dayOffset, formatDay, formatDuration, formatMoney } from "../format";
import { PriceBreakdown } from "./price-breakdown";

function Airline({ offer }: { offer: FlightOffer }) {
  const names = [...new Set(offer.legs.map((l) => l.airline_name ?? l.airline_code ?? "Airline"))];
  return (
    <div className="flex items-center gap-2">
      <span className="flex size-9 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
        {offer.legs[0].airline_code ?? <Plane className="size-4" />}
      </span>
      <div className="grid text-sm">
        <span className="font-medium">{names.join(" + ")}</span>
        <span className="text-xs text-muted-foreground">{offer.legs.map((l) => l.flight_number).join(" · ")}</span>
      </div>
    </div>
  );
}

export function FlightOfferCard({
  offer,
  adults,
  selected,
  onSelect,
}: {
  offer: FlightOffer;
  adults: number;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const first = offer.legs[0];
  const last = offer.legs[offer.legs.length - 1];
  const plusDays = dayOffset(first.departure_local, last.arrival_local);
  const stopsLabel =
    offer.stops === 0 ? "Direct" : `${offer.stops} stop · ${offer.layovers.map((l) => l.airport.code).join(", ")}`;

  return (
    <Card className={cn("gap-0 p-0 transition-shadow", selected && "ring-2 ring-primary")}>
      <div className="grid gap-4 p-4 lg:grid-cols-[14rem_minmax(0,1fr)_auto] lg:items-center">
        <Airline offer={offer} />
        <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3">
          <div className="text-right">
            <div className="text-lg font-semibold tabular-nums">{clockTime(first.departure_local)}</div>
            <div className="text-xs text-muted-foreground">{first.origin.code}</div>
          </div>
          <div className="grid justify-items-center gap-1 text-xs text-muted-foreground">
            <span>{formatDuration(offer.duration_minutes)}</span>
            <span className="relative h-px w-full bg-border">
              {offer.layovers.map((l) => (
                <span key={l.airport.code} className="absolute top-1/2 left-1/2 size-2 -translate-1/2 rounded-full bg-amber-500" />
              ))}
            </span>
            <span className={cn(offer.stops === 0 && "text-emerald-600 dark:text-emerald-400")}>{stopsLabel}</span>
          </div>
          <div>
            <div className="text-lg font-semibold tabular-nums">
              {clockTime(last.arrival_local)}
              {plusDays > 0 ? <sup className="ml-0.5 text-xs text-amber-600">+{plusDays}</sup> : null}
            </div>
            <div className="text-xs text-muted-foreground">{last.destination.code}</div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-4 lg:justify-end">
          <PriceBreakdown ledger={offer.price} caption={adults > 1 ? `total for ${adults} adults` : "per adult"} />
          {onSelect ? (
            <Button onClick={onSelect} disabled={!offer.bookable} variant={selected ? "secondary" : "default"}>
              {selected ? "Selected" : offer.bookable ? "Select" : "Browse only"}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t px-4 py-2">
        <Badge variant="outline">{CABIN_LABELS[first.cabin_class] ?? first.cabin_class}</Badge>
        {offer.self_transfer ? <Badge variant="outline">Different airlines</Badge> : null}
        {(offer.notices ?? []).map((n) => (
          <span key={n} className="text-xs text-muted-foreground">
            {n}
          </span>
        ))}
        <Button variant="ghost" size="sm" className="ml-auto h-7" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          Flight details <ChevronDown className={cn("transition-transform", open && "rotate-180")} />
        </Button>
      </div>

      {open ? (
        <ol className="grid gap-3 border-t bg-muted/30 p-4 text-sm">
          {offer.legs.map((leg, i) => (
            <li key={leg.flight_id} className="grid gap-1">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">
                  {formatDay(leg.departure_local)} · {clockTime(leg.departure_local)} {leg.origin.city_name} ({leg.origin.code})
                  {" → "}
                  {clockTime(leg.arrival_local)} {leg.destination.city_name} ({leg.destination.code})
                </span>
                <span className="text-muted-foreground">{leg.fare ? formatMoney(leg.fare) : "No fare in data"}</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {leg.airline_name} {leg.flight_number} · {formatDuration(leg.duration_minutes)}
                {leg.aircraft ? ` · ${leg.aircraft}` : ""} · times are local at each airport
              </span>
              {offer.layovers[i] ? (
                <span className="mt-1 w-fit rounded bg-amber-500/10 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300">
                  Change planes in {offer.layovers[i].airport.city_name} · {formatDuration(offer.layovers[i].minutes)} layover
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </Card>
  );
}
