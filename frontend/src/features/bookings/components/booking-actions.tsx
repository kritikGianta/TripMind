"use client";

import { CalendarDays, Plane, Star } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useWriteReview } from "@/features/account/self-service";
import { FormError } from "@/features/auth/components/form-error";
import { toQuery, useFlightSearch } from "@/features/search/api";
import { clockTime, formatDuration, formatMoney, todayIso } from "@/features/search/format";

import type { Booking, BookingItem } from "../api";
import { useChangeQuote, useConfirmChange, type ChangeQuote, type PaymentInput } from "../self-service";

export type CardState = { number: string; month: string; year: string; cvc: string; name: string };
export const EMPTY_CARD: CardState = { number: "", month: "", year: "", cvc: "", name: "" };

export function cardPayload(card: CardState): PaymentInput {
  return {
    // Cards are written with spaces, as printed; the API takes digits only.
    card_number: card.number.replace(/\s/g, ""),
    expiry_month: Number(card.month),
    expiry_year: Number(card.year.length === 2 ? `20${card.year}` : card.year),
    cvc: card.cvc,
    cardholder_name: card.name,
  };
}

export function CardFields({ card, onChange, idPrefix = "pay" }: { card: CardState; onChange: (card: CardState) => void; idPrefix?: string }) {
  return (
    <div className="grid gap-3 rounded-sm border p-3">
      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-number`}>Card number</Label>
        <Input id={`${idPrefix}-number`} inputMode="numeric" autoComplete="cc-number" placeholder="4242 4242 4242 4242" value={card.number} onChange={(e) => onChange({ ...card, number: e.target.value })} />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="grid gap-1.5">
          <Label htmlFor={`${idPrefix}-month`}>Month</Label>
          <Input id={`${idPrefix}-month`} inputMode="numeric" placeholder="12" value={card.month} onChange={(e) => onChange({ ...card, month: e.target.value })} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${idPrefix}-year`}>Year</Label>
          <Input id={`${idPrefix}-year`} inputMode="numeric" placeholder="2030" value={card.year} onChange={(e) => onChange({ ...card, year: e.target.value })} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${idPrefix}-cvc`}>CVC</Label>
          <Input id={`${idPrefix}-cvc`} inputMode="numeric" autoComplete="cc-csc" placeholder="123" value={card.cvc} onChange={(e) => onChange({ ...card, cvc: e.target.value })} />
        </div>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-name`}>Name on card</Label>
        <Input id={`${idPrefix}-name`} autoComplete="cc-name" value={card.name} onChange={(e) => onChange({ ...card, name: e.target.value })} />
      </div>
      <p className="text-xs text-muted-foreground">Payments are simulated; no money moves. Test card: 4242 4242 4242 4242.</p>
    </div>
  );
}

function QuoteLines({ quote }: { quote: ChangeQuote }) {
  const row = (label: string, value: string, strong = false) => (
    <div className={`flex justify-between gap-3 ${strong ? "border-t pt-2 font-semibold" : ""}`}>
      <span>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
  const due = quote.amount_due.amount_minor;
  const back = quote.refund_due.amount_minor;
  return (
    <div className="grid gap-1.5 text-sm">
      <p className="text-muted-foreground">
        {quote.current_title} → <span className="font-medium text-foreground">{quote.new_title}</span>
      </p>
      {quote.new_subtitle ? <p className="text-xs text-muted-foreground">{quote.new_subtitle}</p> : null}
      {row("You paid", formatMoney(quote.paid))}
      {quote.new_price ? row("New price", formatMoney(quote.new_price)) : null}
      {row("Change fee", formatMoney(quote.change_fee))}
      {quote.extras_refund.amount_minor ? row("Extras refunded", formatMoney(quote.extras_refund)) : null}
      {back > 0 ? row("We refund you", formatMoney(quote.refund_due), true) : row("You pay now", formatMoney(quote.amount_due), true)}
      {due === 0 && back === 0 ? <p className="text-xs text-muted-foreground">Nothing to pay.</p> : null}
      <p className="text-xs text-muted-foreground">{quote.policy}</p>
    </div>
  );
}

type LegDetails = { origin: { code: string }; destination: { code: string }; departure_local: string; cabin_class: string };

function FlightChooser({ item, adults, onPick, picked }: { item: BookingItem; adults: number; onPick: (id: string) => void; picked: string | null }) {
  const legs = ((item.details as { legs?: LegDetails[] }).legs ?? []) as LegDetails[];
  const first = legs[0];
  const last = legs[legs.length - 1];
  const [date, setDate] = useState(first?.departure_local.slice(0, 10) ?? todayIso());
  const query = first && last ? toQuery({ origin: first.origin.code, destination: last.destination.code, departure_date: date, adults, cabin_class: first.cabin_class }) : null;
  const { data, isFetching } = useFlightSearch(query);
  const offers = (data?.outbound.offers ?? []).filter((offer) => offer.bookable).slice(0, 6);
  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor="change-flight-date">New date</Label>
        <Input id="change-flight-date" type="date" min={todayIso()} value={date} onChange={(e) => setDate(e.target.value)} />
      </div>
      {isFetching && !offers.length ? <Skeleton className="h-24 w-full" /> : null}
      {!isFetching && offers.length === 0 ? <p className="text-sm text-muted-foreground">No flights that day. Try another date.</p> : null}
      <ul className="grid max-h-56 gap-1.5 overflow-y-auto">
        {offers.map((offer) => (
          <li key={offer.id}>
            <button
              type="button"
              aria-pressed={picked === offer.id}
              onClick={() => onPick(offer.id)}
              className={`grid w-full grid-cols-[1fr_auto] gap-2 rounded-sm border p-2 text-left text-sm transition-colors hover:bg-muted ${picked === offer.id ? "border-primary bg-muted" : ""}`}
            >
              <span>
                <span className="font-medium">
                  {clockTime(offer.legs[0].departure_local)} → {clockTime(offer.legs[offer.legs.length - 1].arrival_local)}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {offer.legs.map((leg) => leg.flight_number).join(" + ")} · {formatDuration(offer.duration_minutes)} · {offer.stops === 0 ? "direct" : `${offer.stops} stop`}
                </span>
              </span>
              <span className="font-medium tabular-nums">{formatMoney(offer.price.display_total)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Move a flight to another time, or a stay to other dates: shows the fee and fare difference first. */
export function ChangeDialog({ booking, item, onClose }: { booking: Booking; item: BookingItem | null; onClose: () => void }) {
  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90svh] overflow-y-auto">
        {item ? <ChangeForm key={item.id} booking={booking} item={item} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function ChangeForm({ booking, item, onClose }: { booking: Booking; item: BookingItem; onClose: () => void }) {
  const isFlight = item.kind === "flight";
  const quote = useChangeQuote(booking.id, item.id);
  const confirm = useConfirmChange(booking.id, item.id);
  const [offerId, setOfferId] = useState<string | null>(null);
  const [checkIn, setCheckIn] = useState(item.starts_at.slice(0, 10));
  const [checkOut, setCheckOut] = useState(item.ends_at.slice(0, 10));
  const [card, setCard] = useState(EMPTY_CARD);
  const request = isFlight ? { flight_offer_id: offerId } : { check_in: checkIn, check_out: checkOut };
  const ready = isFlight ? Boolean(offerId) : checkOut > checkIn;
  const due = quote.data?.amount_due.amount_minor ?? 0;

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          {isFlight ? <Plane className="size-4" aria-hidden /> : <CalendarDays className="size-4" aria-hidden />}
          {isFlight ? "Change this flight" : "Change these dates"}
        </DialogTitle>
        <DialogDescription>{item.title}. You&apos;ll see the full cost before anything changes.</DialogDescription>
      </DialogHeader>

      {isFlight ? (
        <FlightChooser
          item={item}
          adults={booking.travellers.length}
          picked={offerId}
          onPick={(id) => {
            setOfferId(id);
            quote.reset();
          }}
        />
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="change-check-in">Check-in</Label>
            <Input id="change-check-in" type="date" min={todayIso()} value={checkIn} onChange={(e) => { setCheckIn(e.target.value); quote.reset(); }} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="change-check-out">Check-out</Label>
            <Input id="change-check-out" type="date" min={checkIn} value={checkOut} onChange={(e) => { setCheckOut(e.target.value); quote.reset(); }} />
          </div>
        </div>
      )}

      {quote.data ? (
        quote.data.allowed ? (
          <QuoteLines quote={quote.data} />
        ) : (
          <p className="text-sm text-destructive">{quote.data.reason ?? "This can't be changed."}</p>
        )
      ) : null}
      {quote.data?.allowed && due > 0 ? <CardFields card={card} onChange={setCard} idPrefix="change" /> : null}
      <FormError error={quote.error ?? confirm.error} />

      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Keep it as it is
        </Button>
        {quote.data?.allowed ? (
          <Button
            disabled={confirm.isPending}
            onClick={() =>
              confirm.mutate(
                { ...request, expected_amount_due_minor: due, payment: due > 0 ? cardPayload(card) : null },
                {
                  onSuccess: () => {
                    toast.success("Done. Your booking has been updated.");
                    onClose();
                  },
                },
              )
            }
          >
            {confirm.isPending ? "Changing…" : due > 0 ? `Pay ${formatMoney(quote.data.amount_due)} and change` : "Confirm change"}
          </Button>
        ) : (
          <Button disabled={!ready || quote.isPending} onClick={() => quote.mutate(request)}>
            {quote.isPending ? "Checking…" : "See the cost"}
          </Button>
        )}
      </DialogFooter>
    </>
  );
}

const TRAVELLER_TYPES = ["couple", "family", "solo", "business", "friends"] as const;

export function ReviewDialog({ booking, item, onClose }: { booking: Booking; item: BookingItem | null; onClose: () => void }) {
  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>{item ? <ReviewForm key={item.id} booking={booking} item={item} onClose={onClose} /> : null}</DialogContent>
    </Dialog>
  );
}

function ReviewForm({ booking, item, onClose }: { booking: Booking; item: BookingItem; onClose: () => void }) {
  const write = useWriteReview(booking.id, item.id);
  const [rating, setRating] = useState(8);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [type, setType] = useState("none");
  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Star className="size-4" aria-hidden /> How was your stay?
        </DialogTitle>
        <DialogDescription>{item.title}. Your review shows as a verified stay.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="review-rating">Rating out of 10</Label>
            <Input id="review-rating" type="number" min={1} max={10} value={rating} onChange={(e) => setRating(Number(e.target.value))} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="review-type">You travelled as</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id="review-type" className="w-full capitalize">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Prefer not to say</SelectItem>
                {TRAVELLER_TYPES.map((value) => (
                  <SelectItem key={value} value={value} className="capitalize">
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="review-title">Title (optional)</Label>
          <Input id="review-title" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="review-text">Your review</Label>
          <Textarea id="review-text" rows={4} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
          <p className="text-xs text-muted-foreground">At least 20 characters. Please don&apos;t include personal details.</p>
        </div>
        <FormError error={write.error} />
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Not now
        </Button>
        <Button
          disabled={write.isPending || text.trim().length < 20 || rating < 1 || rating > 10}
          onClick={() =>
            write.mutate(
              { rating, title: title.trim() || null, text: text.trim(), traveller_type: type === "none" ? null : (type as (typeof TRAVELLER_TYPES)[number]) },
              {
                onSuccess: () => {
                  toast.success("Thanks. Your review is live.");
                  onClose();
                },
              },
            )
          }
        >
          Publish review
        </Button>
      </DialogFooter>
    </>
  );
}
