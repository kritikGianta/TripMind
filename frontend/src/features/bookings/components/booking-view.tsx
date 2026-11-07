"use client";

import { AlertCircle, BedDouble, CheckCircle2, Clock, CreditCard, Plane, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/features/search/format";
import { RecoveryBanner } from "@/features/recovery/components/recovery-view";
import { errorMessage } from "@/lib/api/errors";

import { useBooking, useCancel, useCancellationQuote, usePay, type Booking, type BookingItem } from "../api";

const STATUS: Record<string, { label: string; className: string }> = {
  held: { label: "Awaiting payment", className: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  payment_failed: { label: "Payment failed", className: "bg-destructive/15 text-destructive" },
  confirmed: { label: "Confirmed", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  cancelled: { label: "Cancelled", className: "bg-muted text-muted-foreground" },
  expired: { label: "Hold expired", className: "bg-muted text-muted-foreground" },
  released: { label: "Released", className: "bg-muted text-muted-foreground" },
  replaced: { label: "Replaced", className: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, className: "" };
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.className}`}>{s.label}</span>;
}

const when = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function Countdown({ until, onExpire }: { until: string; onExpire: () => void }) {
  const [left, setLeft] = useState(() => Date.parse(until) - Date.now());
  useEffect(() => {
    const id = setInterval(() => {
      const ms = Date.parse(until) - Date.now();
      setLeft(ms);
      if (ms <= 0) {
        clearInterval(id);
        onExpire();
      }
    }, 1000);
    return () => clearInterval(id);
  }, [until, onExpire]);
  const s = Math.max(0, Math.floor(left / 1000));
  return (
    <span className="tabular-nums font-semibold">
      {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}
    </span>
  );
}

function PaymentCard({ booking, onExpire }: { booking: Booking; onExpire: () => void }) {
  const pay = usePay(booking.id);
  const [card, setCard] = useState({ number: "", month: "", year: "", cvc: "", name: "" });

  function submit(event: FormEvent) {
    event.preventDefault();
    pay.mutate(
      {
        key: crypto.randomUUID(),
        input: {
          card_number: card.number,
          expiry_month: Number(card.month),
          expiry_year: Number(card.year.length === 2 ? `20${card.year}` : card.year),
          cvc: card.cvc,
          cardholder_name: card.name,
        },
      },
      { onSuccess: () => toast.success("Payment received. Your booking is confirmed.") },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="size-4" /> Pay {formatMoney(booking.total)}
        </CardTitle>
        <CardDescription className="flex items-center gap-1">
          <Clock className="size-3.5" /> Held for you for <Countdown until={booking.hold_expires_at} onExpire={onExpire} />
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-3" noValidate>
          <div className="grid gap-1.5">
            <Label htmlFor="card-number">Card number</Label>
            <Input id="card-number" inputMode="numeric" autoComplete="cc-number" placeholder="4242 4242 4242 4242"
              value={card.number} onChange={(e) => setCard({ ...card, number: e.target.value })} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="card-month">Month</Label>
              <Input id="card-month" inputMode="numeric" placeholder="12" value={card.month} onChange={(e) => setCard({ ...card, month: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="card-year">Year</Label>
              <Input id="card-year" inputMode="numeric" placeholder="2030" value={card.year} onChange={(e) => setCard({ ...card, year: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="card-cvc">CVC</Label>
              <Input id="card-cvc" inputMode="numeric" autoComplete="cc-csc" placeholder="123" value={card.cvc} onChange={(e) => setCard({ ...card, cvc: e.target.value })} />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="card-name">Name on card</Label>
            <Input id="card-name" autoComplete="cc-name" value={card.name} onChange={(e) => setCard({ ...card, name: e.target.value })} />
          </div>
          {pay.error ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{errorMessage(pay.error)}</AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" size="lg" disabled={pay.isPending}>
            {pay.isPending ? "Processing…" : `Pay ${formatMoney(booking.total)}`}
          </Button>
          <p className="text-xs text-muted-foreground">
            Payments are simulated; no money moves. Test cards: 4242 4242 4242 4242 succeeds, 4000 0000 0000 0002 is
            declined. Only the last four digits are stored.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function CancelDialog({ booking, items, onClose }: { booking: Booking; items: BookingItem[] | null; onClose: () => void }) {
  const ids = items ? items.map((i) => i.id) : null;
  const quote = useCancellationQuote(booking.id, items === null ? null : ids ?? []);
  const cancel = useCancel(booking.id);
  return (
    <Dialog open={items !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel {items && items.length === 1 ? items[0].title : "booking"}?</DialogTitle>
          <DialogDescription>Refunds follow the policy shown when you booked.</DialogDescription>
        </DialogHeader>
        {quote.data ? (
          <div className="grid gap-2 text-sm">
            {quote.data.lines.map((line) => (
              <div key={line.item_id} className="flex justify-between gap-3">
                <span>
                  {line.title}
                  <span className="block text-xs text-muted-foreground">{line.reason}</span>
                </span>
                <span className="tabular-nums">{formatMoney(line.refund)}</span>
              </div>
            ))}
            <div className="flex justify-between border-t pt-2 font-semibold">
              <span>Refund</span>
              <span className="tabular-nums">{formatMoney(quote.data.total_refund)}</span>
            </div>
          </div>
        ) : (
          <Skeleton className="h-16 w-full" />
        )}
        {cancel.error ? <p className="text-sm text-destructive">{errorMessage(cancel.error)}</p> : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Keep it
          </Button>
          <Button
            variant="destructive"
            disabled={!quote.data || cancel.isPending}
            onClick={() =>
              cancel.mutate(ids, {
                onSuccess: () => {
                  toast.success("Cancelled.");
                  onClose();
                },
              })
            }
          >
            {cancel.isPending ? "Cancelling…" : "Confirm cancellation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ItemCard({ item, canCancel, onCancel }: { item: BookingItem; canCancel: boolean; onCancel: () => void }) {
  const live = item.status === "held" || item.status === "confirmed";
  return (
    <div className="grid gap-2 border-b pb-4 last:border-0 last:pb-0 md:grid-cols-[1fr_auto] md:items-start">
      <div className="grid gap-1">
        <div className="flex flex-wrap items-center gap-2 font-medium">
          {item.kind === "flight" ? <Plane className="size-4" /> : <BedDouble className="size-4" />}
          {item.title} <StatusBadge status={item.status} />
        </div>
        <p className="text-sm text-muted-foreground">{item.subtitle}</p>
        <p className="text-xs text-muted-foreground">
          {when.format(new Date(item.starts_at))} → {when.format(new Date(item.ends_at))}
        </p>
        <p className="text-xs text-muted-foreground">{item.policy}</p>
      </div>
      <div className="grid justify-items-end gap-2">
        <span className="font-semibold tabular-nums">{formatMoney(item.price)}</span>
        {canCancel && live ? (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel this
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export function BookingView() {
  const { id } = useParams<{ id: string }>();
  const { data: booking, error, isPending, refetch } = useBooking(id);
  const [cancelItems, setCancelItems] = useState<BookingItem[] | null>(null);

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !booking) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  const open = booking.status === "held" || booking.status === "payment_failed";
  const liveItems = booking.items.filter((i) => i.status === "held" || i.status === "confirmed");

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_22rem]">
      <div className="grid content-start gap-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">Booking {booking.reference}</h1>
          <StatusBadge status={booking.status} />
        </div>

        <RecoveryBanner bookingId={booking.id} />
        {booking.status === "confirmed" ? (
          <Alert>
            <CheckCircle2 className="text-emerald-600" />
            <AlertTitle>You&apos;re booked</AlertTitle>
            <AlertDescription>
              Confirmation sent to {booking.contact_email}. Your reference is {booking.reference}.
            </AlertDescription>
          </Alert>
        ) : booking.status === "expired" ? (
          <Alert>
            <XCircle />
            <AlertTitle>The hold expired</AlertTitle>
            <AlertDescription>Nothing was charged and the seats or rooms were released. Search again to book.</AlertDescription>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>What&apos;s booked</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {booking.items.map((item) => (
              <ItemCard key={item.id} item={item} canCancel={booking.can_cancel && booking.items.length > 1}
                onCancel={() => setCancelItems([item])} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Travellers</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-1 text-sm">
            {booking.travellers.map((t, i) => (
              <p key={i}>
                {t.first_name} {t.last_name}
                {t.date_of_birth ? <span className="text-muted-foreground"> · born {t.date_of_birth}</span> : null}
              </p>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="grid gap-3 border-l pl-4 text-sm">
              {booking.events.map((e, i) => (
                <li key={i} className="relative">
                  <span className="absolute top-1.5 -left-[1.3rem] size-2 rounded-full bg-primary" />
                  <p>{e.message}</p>
                  <p className="text-xs text-muted-foreground">{when.format(new Date(e.occurred_at))}</p>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      <aside className="grid content-start gap-4 md:sticky md:top-20">
        {open ? <PaymentCard booking={booking} onExpire={() => void refetch()} /> : null}
        <Card>
          <CardHeader>
            <CardTitle>Payment summary</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <div className="flex justify-between font-semibold">
              <span>Total</span>
              <span className="tabular-nums">{formatMoney(booking.total)}</span>
            </div>
            {booking.payments.map((p, i) => (
              <div key={i} className="flex justify-between text-muted-foreground">
                <span>
                  {p.card_brand} ·{p.card_last4} {p.status === "failed" ? `declined (${p.failure_code})` : "paid"}
                </span>
                <span className="tabular-nums">{formatMoney(p.amount)}</span>
              </div>
            ))}
            {booking.refunds.map((r, i) => (
              <div key={i} className="flex justify-between text-emerald-700 dark:text-emerald-400">
                <span>Refund</span>
                <span className="tabular-nums">−{formatMoney(r.amount)}</span>
              </div>
            ))}
            {booking.fx_note ? <p className="text-xs text-muted-foreground">{booking.fx_note}</p> : null}
            <Button asChild variant="outline" className="mt-2">
              <Link href={`/trips/${booking.trip_id}`}>View trip</Link>
            </Button>
            {booking.can_cancel ? (
              <Button variant="ghost" className="text-destructive" onClick={() => setCancelItems(liveItems)}>
                {open ? "Cancel and release" : "Cancel booking"}
              </Button>
            ) : null}
            {booking.status === "confirmed" ? (
              <Badge variant="outline" className="w-fit">
                Demo booking: no real ticket is issued
              </Badge>
            ) : null}
          </CardContent>
        </Card>
      </aside>
      <CancelDialog booking={booking} items={cancelItems} onClose={() => setCancelItems(null)} />
    </div>
  );
}
