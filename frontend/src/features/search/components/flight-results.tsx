"use client";

import { AlertCircle, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { toQuery, useFlightSearch, type FlightOffer, type FlightResults } from "../api";
import { CABIN_LABELS, formatDay, formatMoney } from "../format";
import { CheckboxFacet, FilterGroup, PriceFacet, SortBar, useUrlState } from "./filters";
import { FlightOfferCard } from "./flight-offer-card";
import { SearchPanel } from "./search-panel";

const SORTS = [
  { value: "best", label: "Best" },
  { value: "cheapest", label: "Cheapest" },
  { value: "fastest", label: "Fastest" },
  { value: "earliest", label: "Earliest" },
] as const;
type Sort = (typeof SORTS)[number]["value"];

function Filters({ results }: { results: FlightResults }) {
  const { params, update } = useUrlState();
  const facets = results.facets;
  const stops = params.get("stops");
  return (
    <div className="grid gap-4">
      <FilterGroup title="Stops">
        <CheckboxFacet
          name="stops"
          options={facets.stops.filter((o) => o.value !== "2")}
          selected={stops === "0" ? ["0"] : []}
          onChange={(values) => update({ stops: values.includes("0") ? "0" : null })}
          showPrice
        />
        <p className="text-xs text-muted-foreground">Tick Direct to hide connections.</p>
      </FilterGroup>
      <FilterGroup title="Airlines">
        <CheckboxFacet
          name="airline"
          options={facets.airlines}
          selected={params.getAll("airline")}
          onChange={(values) => update({ airline: values })}
          showPrice
        />
      </FilterGroup>
      <FilterGroup title="Departure time">
        <CheckboxFacet
          name="window"
          options={facets.departure_windows}
          selected={params.getAll("window")}
          onChange={(values) => update({ window: values })}
        />
      </FilterGroup>
      <FilterGroup title="Price">
        <PriceFacet
          range={facets.price_range}
          value={params.get("maxPrice") ? Number(params.get("maxPrice")) : null}
          onCommit={(max) => update({ maxPrice: max === null ? null : String(max) })}
          caption="Total price"
        />
      </FilterGroup>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => update({ stops: null, airline: [], window: [], maxPrice: null })}
      >
        Clear filters
      </Button>
    </div>
  );
}

function OfferList({
  results,
  adults,
  selectedId,
  onSelect,
}: {
  results: FlightResults;
  adults: number;
  selectedId: string | null;
  onSelect: (offer: FlightOffer) => void;
}) {
  if (!results.offers.length) {
    return (
      <Card className="p-8 text-center text-sm text-muted-foreground">
        {results.unfiltered_total
          ? "No flights match these filters. Try clearing some of them."
          : "No flights found for this route and date in the dataset."}
      </Card>
    );
  }
  return (
    <div className="grid gap-3">
      {results.offers.map((offer) => (
        <FlightOfferCard
          key={offer.id}
          offer={offer}
          adults={adults}
          selected={offer.id === selectedId}
          onSelect={() => onSelect(offer)}
        />
      ))}
    </div>
  );
}

export function FlightResultsView() {
  const { params, update } = useUrlState();
  const from = params.get("from");
  const to = params.get("to");
  const depart = params.get("depart");
  const ret = params.get("return");
  const adults = Number(params.get("adults") ?? 1);
  const cabin = params.get("cabin") ?? "economy";
  const sort = (params.get("sort") ?? "best") as Sort;

  const query = useMemo(() => {
    if (!from || !to || !depart) return null;
    return toQuery({
      origin: from,
      destination: to,
      departure_date: depart,
      return_date: ret ?? undefined,
      adults,
      cabin_class: cabin,
      max_stops: params.get("stops") ?? undefined,
      airlines: params.getAll("airline"),
      departure_windows: params.getAll("window"),
      max_price: params.get("maxPrice") ?? undefined,
      sort,
    });
  }, [from, to, depart, ret, adults, cabin, sort, params]);

  const { data, error, isPending, isFetching } = useFlightSearch(query);
  const [leg, setLeg] = useState<"outbound" | "inbound">("outbound");
  const [picked, setPicked] = useState<{ outbound?: FlightOffer; inbound?: FlightOffer }>({});

  const panel = (
    <SearchPanel
      defaultTab="flights"
      flight={{
        from: from ? { value: from, label: params.get("fromLabel") ?? from } : null,
        to: to ? { value: to, label: params.get("toLabel") ?? to } : null,
        depart: depart ?? "",
        ret: ret ?? "",
        adults,
        cabin,
      }}
    />
  );

  if (!query) {
    return <div className="mx-auto w-full max-w-6xl px-4 py-8">{panel}</div>;
  }

  const current = data ? (leg === "inbound" && data.inbound ? data.inbound : data.outbound) : null;
  const tripTotal =
    picked.outbound?.price.display_total &&
    (!data?.inbound || picked.inbound?.price.display_total)
      ? {
          amount_minor:
            picked.outbound.price.display_total.amount_minor +
            (picked.inbound?.price.display_total?.amount_minor ?? 0),
          currency: picked.outbound.price.display_total.currency,
        }
      : null;

  function select(offer: FlightOffer) {
    setPicked((p) => ({ ...p, [leg]: offer }));
    if (leg === "outbound" && data?.inbound) setLeg("inbound");
  }

  const filters = current ? <Filters results={current} /> : null;

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
              <h1 className="text-lg font-semibold">
                {leg === "inbound" ? "Choose your return" : "Choose your outbound flight"}
              </h1>
              {current ? (
                <p className="text-sm text-muted-foreground">
                  {current.origin?.city_name} → {current.destination?.city_name} · {formatDay(current.date)} ·{" "}
                  {adults} adult{adults > 1 ? "s" : ""} · {CABIN_LABELS[cabin]} · {current.total} of {current.unfiltered_total}{" "}
                  options
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

          {data?.inbound ? (
            <div className="grid grid-cols-2 gap-2">
              {(["outbound", "inbound"] as const).map((key) => (
                <Button
                  key={key}
                  variant={leg === key ? "default" : "outline"}
                  onClick={() => setLeg(key)}
                  className="h-auto flex-col items-start py-2"
                >
                  <span className="text-xs opacity-80">{key === "outbound" ? "1. Outbound" : "2. Return"}</span>
                  <span>
                    {picked[key] ? `${picked[key]!.legs[0].flight_number} · ${formatMoney(picked[key]!.price.display_total)}` : "Not chosen"}
                  </span>
                </Button>
              ))}
            </div>
          ) : null}

          {isPending ? (
            <div className="grid gap-3">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-32 w-full" />
              ))}
            </div>
          ) : current ? (
            <OfferList results={current} adults={adults} selectedId={picked[leg]?.id ?? null} onSelect={select} />
          ) : null}
        </section>
      </div>

      {picked.outbound ? (
        <div className="sticky bottom-4 z-20 mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-3 rounded-xl border bg-background/95 p-4 shadow-lg backdrop-blur">
          <div className="text-sm">
            <p className="font-medium">
              {picked.outbound.legs[0].origin.code} → {picked.outbound.legs.at(-1)!.destination.code}
              {data?.inbound ? (picked.inbound ? " and back" : " · now choose your return") : ""}
            </p>
            <p className="text-muted-foreground">
              {tripTotal ? `≈ ${formatMoney(tripTotal)} before taxes and fees` : "Choose both flights to see the trip total"}
            </p>
          </div>
          <Button
            disabled={!tripTotal}
            onClick={() => toast.info("Checkout is the next build step. Your selection is kept on this page.")}
          >
            Continue
          </Button>
        </div>
      ) : null}
    </div>
  );
}
