"use client";

import { Armchair, AlertCircle, BedDouble, CalendarClock, CheckCircle2, Clock, CreditCard, LifeBuoy, Plane, Star, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/features/search/format";
import { RecoveryBanner } from "@/features/recovery/components/recovery-view";
import { errorMessage } from "@/lib/api/errors";

import { useBooking, useCancel, useCancellationQuote, usePay, type Booking, type BookingItem } from "../api";
import { ChangeDialog, ReviewDialog } from "./booking-actions";

const STATUS: Record<string, { label: string; className: string }> = {
  held: { label: "Not confirmed yet", className: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  payment_failed: { label: "Not confirmed", className: "bg-destructive/15 text-destructive" },
  confirmed: { label: "Confirmed", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  cancelled: { label: "Cancelled", className: "bg-muted text-muted-foreground" },
  expired: { label: "Expired", className: "bg-muted text-muted-foreground" },
  released: { label: "Released", className: "bg-muted text-muted-foreground" },
  replaced: { label: "Replaced", className: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, className: "" };
  return <span className={`rounded-full px-2 py-0.5 font-sans text-xs font-medium not-italic ${s.className}`}>{s.label}</span>;
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
  // One key per page visit: a double click or a retry confirms once (the API is idempotent).
  const [key] = useState(() => crypto.randomUUID());

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="size-4" /> Confirm {formatMoney(booking.total)}
        </CardTitle>
        <CardDescription className="flex items-center gap-1">
          <Clock className="size-3.5" /> Confirm within <Countdown until={booking.hold_expires_at} onExpire={onExpire} />
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {pay.error ? (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertDescription>{errorMessage(pay.error)}</AlertDescription>
          </Alert>
        ) : null}
        <Button
          size="lg"
          disabled={pay.isPending}
          onClick={() => pay.mutate({ key, input: {} }, { onSuccess: () => toast.success("Your booking is confirmed.") })}
        >
          {pay.isPending ? "Confirming…" : "Confirm booking"}
        </Button>
        <p className="text-xs text-muted-foreground">No payment is taken: confirming books the seats and rooms.</p>
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

function hasEnded(item: BookingItem) {
  return Date.parse(item.ends_at) < Date.now();
}

function ItemCard({
  item,
  bookingId,
  canCancel,
  onCancel,
  onChange,
  onReview,
}: {
  item: BookingItem;
  bookingId: string;
  canCancel: boolean;
  onCancel: () => void;
  onChange: () => void;
  onReview: () => void;
}) {
  const live = item.status === "held" || item.status === "confirmed";
  const confirmed = item.status === "confirmed";
  const ended = hasEnded(item);
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
        {item.extras?.length ? (
          <ul className="flex flex-wrap gap-1.5 pt-1">
            {item.extras.map((extra) => (
              <li key={extra.id}>
                <Badge variant="secondary">
                  {extra.traveller_name}: {extra.label}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}
        {confirmed ? (
          <div className="flex flex-wrap gap-2 pt-1">
            {item.kind === "flight" && !ended ? (
              <Button asChild variant="outline" size="sm">
                <Link href={`/bookings/${bookingId}/extras/${item.id}`}>
                  <Armchair /> Seats and extras
                </Link>
              </Button>
            ) : null}
            {!ended ? (
              <Button variant="outline" size="sm" onClick={onChange}>
                <CalendarClock /> {item.kind === "flight" ? "Change flight" : "Change dates"}
              </Button>
            ) : null}
            {item.kind !== "flight" && ended ? (
              <Button variant="outline" size="sm" onClick={onReview}>
                <Star /> Write a review
              </Button>
            ) : null}
          </div>
        ) : null}
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
  const [changeItem, setChangeItem] = useState<BookingItem | null>(null);
  const [reviewItem, setReviewItem] = useState<BookingItem | null>(null);
  // The account page links here with ?review= to open the review form straight away.
  const reviewFromLink = useSearchParams().get("review");
  const [linkHandled, setLinkHandled] = useState(false);

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
  const linkedReview = !linkHandled && reviewFromLink ? booking.items.find((i) => i.id === reviewFromLink) ?? null : null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
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
            <AlertTitle>This booking was not confirmed</AlertTitle>
            <AlertDescription>The seats or rooms were released. Search again to book.</AlertDescription>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>What&apos;s booked</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {booking.items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                bookingId={booking.id}
                canCancel={booking.can_cancel && booking.items.length > 1}
                onCancel={() => setCancelItems([item])}
                onChange={() => setChangeItem(item)}
                onReview={() => setReviewItem(item)}
              />
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

      <aside className="grid content-start gap-4 lg:sticky lg:top-20">
        {open ? <PaymentCard booking={booking} onExpire={() => void refetch()} /> : null}
        <Card>
          <CardHeader>
            <CardTitle>Confirmation</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            {booking.discount ? (
              <div className="flex justify-between text-emerald-700 dark:text-emerald-400">
                <span>Promo {booking.promo_code}</span>
                <span className="tabular-nums">−{formatMoney(booking.discount)}</span>
              </div>
            ) : null}
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
            {booking.status === "confirmed" || booking.status === "cancelled" ? (
              <Button asChild variant="outline">
                <Link href={`/bookings/${booking.id}/invoice`}>Invoice and itinerary</Link>
              </Button>
            ) : null}
            {booking.can_cancel ? (
              <Button variant="ghost" className="text-destructive" onClick={() => setCancelItems(liveItems)}>
                {open ? "Cancel and release" : "Cancel booking"}
              </Button>
            ) : null}
            <Button asChild variant="ghost">
              <Link href={`/support/new?booking=${booking.id}`}>
                <LifeBuoy /> Get help with this booking
              </Link>
            </Button>
            {booking.status === "confirmed" ? (
              <Badge variant="outline" className="w-fit">
                Demo booking: no real ticket is issued
              </Badge>
            ) : null}
          </CardContent>
        </Card>
      </aside>
      <CancelDialog booking={booking} items={cancelItems} onClose={() => setCancelItems(null)} />
      <ChangeDialog booking={booking} item={changeItem} onClose={() => setChangeItem(null)} />
      <ReviewDialog
        booking={booking}
        item={reviewItem ?? linkedReview}
        onClose={() => {
          setReviewItem(null);
          setLinkHandled(true);
        }}
      />
    </div>
  );
}
