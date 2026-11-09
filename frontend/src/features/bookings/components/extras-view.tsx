"use client";

import { ArrowLeft, Armchair, Luggage, Utensils } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FormError } from "@/features/auth/components/form-error";
import { formatMoney } from "@/features/search/format";

import { useExtrasCatalog, useExtrasQuote, usePurchaseExtras, useSeatMap, type ExtrasCatalog, type Selection } from "../self-service";
import { CardFields, cardPayload, EMPTY_CARD } from "./booking-actions";

type Kind = Selection["kind"];
const NONE = "none";

function keyOf(flightId: string, travellerId: string, kind: Kind) {
  return `${flightId}|${travellerId}|${kind}`;
}

function toSelections(state: Record<string, string>): Selection[] {
  return Object.entries(state).flatMap(([key, code]) => {
    if (!code || code === NONE) return [];
    const [flight_id, traveller_id, kind] = key.split("|");
    return [{ flight_id, traveller_id, kind: kind as Kind, code }];
  });
}

function SeatPicker({
  bookingId,
  itemId,
  flightId,
  travellerId,
  picked,
  takenByParty,
  onPick,
}: {
  bookingId: string;
  itemId: string;
  flightId: string;
  travellerId: string;
  picked: string | null;
  takenByParty: Set<string>;
  onPick: (code: string | null) => void;
}) {
  const { data: map, isPending, error } = useSeatMap(bookingId, itemId, flightId);
  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error || !map) return <FormError error={error} />;
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        {map.aircraft ? `${map.aircraft} · ` : ""}
        {map.note}
      </p>
      <ul className="tm-seat-legend" aria-label="Seat colours">
        <li><span className="tm-seat" data-sample /> Free to pick</li>
        <li><span className="tm-seat" data-sample data-state="picked" /> Your choice</li>
        <li><span className="tm-seat" data-sample data-state="taken" /> Taken</li>
      </ul>
      <div className="tm-seat-map" role="group" aria-label={`Seats on ${map.flight_number}`}>
        <div className="tm-seat-row" aria-hidden>
          <span className="tm-seat-number" />
          {map.groups.map((group, index) => (
            <span key={group} className={`tm-seat-group${index ? " tm-seat-group--gap" : ""}`}>
              {group.split("").map((letter) => (
                <span key={letter} className="tm-seat-letter">{letter}</span>
              ))}
            </span>
          ))}
        </div>
        {map.rows.map((row) => (
          <div key={row.row} className="tm-seat-row">
            <span className="tm-seat-number">{row.row}</span>
            {map.groups.map((group, index) => (
              <span key={group} className={`tm-seat-group${index ? " tm-seat-group--gap" : ""}`}>
                {group.split("").map((letter) => {
                  const seat = row.seats.find((s) => s.letter === letter);
                  if (!seat) return <span key={letter} className="tm-seat" data-state="none" />;
                  const mine = seat.code === picked;
                  const taken = (!seat.available && seat.traveller_id !== travellerId) || (takenByParty.has(seat.code) && !mine);
                  return (
                    <button
                      key={seat.code}
                      type="button"
                      className="tm-seat"
                      data-state={mine ? "picked" : taken ? "taken" : undefined}
                      disabled={taken}
                      aria-pressed={mine}
                      aria-label={`Seat ${seat.code}, ${seat.position}, ${seat.zone}, ${formatMoney(seat.price)}`}
                      title={`${seat.code} · ${seat.zone} · ${formatMoney(seat.price)}`}
                      onClick={() => onPick(mine ? null : seat.code)}
                    >
                    </button>
                  );
                })}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function ExtrasForm({ bookingId, itemId, catalog }: { bookingId: string; itemId: string; catalog: ExtrasCatalog }) {
  const router = useRouter();
  const [flightId, setFlightId] = useState(catalog.flights[0]?.flight_id ?? "");
  const [travellerId, setTravellerId] = useState(catalog.travellers[0]?.id ?? "");
  const [choices, setChoices] = useState<Record<string, string>>(() =>
    Object.fromEntries(catalog.selected.map((extra) => [keyOf(extra.flight_id, extra.traveller_id, extra.kind as Kind), extra.code])),
  );
  const [card, setCard] = useState(EMPTY_CARD);
  const selections = useMemo(() => toSelections(choices), [choices]);
  const quoteQuery = useExtrasQuote(bookingId, itemId, selections);
  const quote = selections.length ? quoteQuery : { data: undefined, error: null };
  const purchase = usePurchaseExtras(bookingId, itemId);
  const flight = catalog.flights.find((f) => f.flight_id === flightId) ?? catalog.flights[0];
  const total = quote.data?.total.amount_minor ?? 0;

  const set = (kind: Kind, code: string | null) =>
    setChoices((current) => ({ ...current, [keyOf(flightId, travellerId, kind)]: code ?? NONE }));
  const current = (kind: Kind) => choices[keyOf(flightId, travellerId, kind)] ?? NONE;

  // Seats another traveller in this party has picked on this flight are off limits.
  const takenByParty = new Set(
    Object.entries(choices)
      .filter(([key, code]) => key.startsWith(`${flightId}|`) && key.endsWith("|seat") && !key.includes(`|${travellerId}|`) && code !== NONE)
      .map(([, code]) => code),
  );

  const seatChoice = current("seat");

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">
      <div className="grid content-start gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Flight</Label>
            <Tabs value={flightId} onValueChange={setFlightId}>
              <TabsList className="h-auto w-full flex-wrap justify-start">
                {catalog.flights.map((f) => (
                  <TabsTrigger key={f.flight_id} value={f.flight_id} className="flex-none">
                    {f.flight_number} · {f.route}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
          <div className="grid gap-1.5">
            <Label>Traveller</Label>
            <Tabs value={travellerId} onValueChange={setTravellerId}>
              <TabsList className="h-auto w-full flex-wrap justify-start">
                {catalog.travellers.map((t) => (
                  <TabsTrigger key={t.id} value={t.id} className="flex-none">
                    {t.name}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Armchair className="size-4" aria-hidden /> Seat
              {seatChoice !== NONE ? <span className="text-sm not-italic text-muted-foreground">Selected: {seatChoice}</span> : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {flight ? (
              <SeatPicker
                key={flight.flight_id}
                bookingId={bookingId}
                itemId={itemId}
                flightId={flight.flight_id}
                travellerId={travellerId}
                picked={seatChoice === NONE ? null : seatChoice}
                takenByParty={takenByParty}
                onPick={(code) => set("seat", code)}
              />
            ) : null}
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          {([
            { kind: "baggage" as Kind, title: "Extra baggage", icon: Luggage, options: flight?.baggage ?? [] },
            { kind: "meal" as Kind, title: "Meal", icon: Utensils, options: flight?.meals ?? [] },
          ]).map(({ kind, title, icon: Icon, options }) => (
            <Card key={kind}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Icon className="size-4" aria-hidden /> {title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Select value={current(kind)} onValueChange={(value) => set(kind, value)}>
                  <SelectTrigger aria-label={title} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE}>None</SelectItem>
                    {options.map((option) => (
                      <SelectItem key={option.code} value={option.code}>
                        {option.label} · {formatMoney(option.price)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <aside className="grid content-start gap-3 lg:sticky lg:top-20">
        <Card>
          <CardHeader>
            <CardTitle>Your extras</CardTitle>
            <CardDescription>{catalog.policy}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            {quote.data?.lines.length ? (
              quote.data.lines.map((line) => (
                <div key={`${line.flight_id}${line.traveller_id}${line.kind}`} className="flex justify-between gap-3">
                  <span>
                    {line.label}
                    {line.unchanged ? <span className="block text-xs text-muted-foreground">Already yours</span> : null}
                  </span>
                  <span className="tabular-nums">{formatMoney(line.charge)}</span>
                </div>
              ))
            ) : (
              <p className="text-muted-foreground">Nothing chosen yet.</p>
            )}
            <div className="flex justify-between border-t pt-2 font-semibold">
              <span>To pay</span>
              <span className="tabular-nums">{quote.data ? formatMoney(quote.data.total) : "—"}</span>
            </div>
            {total > 0 ? <CardFields card={card} onChange={setCard} idPrefix="extras" /> : null}
            <FormError error={purchase.error ?? quote.error} />
            <Button
              disabled={purchase.isPending || !quote.data || !selections.length}
              onClick={() =>
                purchase.mutate(
                  { selections, expected_total_minor: total, payment: total > 0 ? cardPayload(card) : null },
                  {
                    onSuccess: () => {
                      toast.success("Your extras are saved.");
                      router.push(`/bookings/${bookingId}`);
                    },
                  },
                )
              }
            >
              {purchase.isPending ? "Saving…" : total > 0 ? `Pay ${formatMoney(quote.data?.total)}` : "Save choices"}
            </Button>
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

export function ExtrasView() {
  const { id, itemId } = useParams<{ id: string; itemId: string }>();
  const { data, error, isPending } = useExtrasCatalog(id, itemId);
  return (
    <div className="grid gap-4">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link href={`/bookings/${id}`}>
          <ArrowLeft /> Back to the booking
        </Link>
      </Button>
      <h1>Seats and extras</h1>
      {isPending ? <Skeleton className="h-96 w-full" /> : null}
      {error ? <FormError error={error} /> : null}
      {data && !data.open ? (
        <Alert>
          <AlertDescription>{data.reason ?? "Seats and extras are closed for this flight."}</AlertDescription>
        </Alert>
      ) : null}
      {data?.open ? <ExtrasForm bookingId={id} itemId={itemId} catalog={data} /> : null}
    </div>
  );
}
