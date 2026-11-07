"use client";

import { AlertCircle, AlertTriangle, CheckCircle2, Plane } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/features/search/format";
import { errorMessage } from "@/lib/api/errors";

import { useAccept, useBookingCases, useCase, type RecoveryOption } from "../api";

/** Banner on the booking page while a disruption needs the traveller's decision. */
export function RecoveryBanner({ bookingId }: { bookingId: string }) {
  const { data } = useBookingCases(bookingId);
  const open = data?.items.filter((c) => c.status === "open") ?? [];
  if (!open.length) return null;
  return (
    <>
      {open.map((c) => (
        <Alert key={c.id} variant="destructive">
          <AlertTriangle />
          <AlertTitle>Action needed</AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>{c.summary}</span>
            <Button asChild size="sm" className="w-fit">
              <Link href={`/recovery/${c.id}`}>Choose what to do</Link>
            </Button>
          </AlertDescription>
        </Alert>
      ))}
    </>
  );
}

function OptionCard({ option, onChoose, busy, chosen, resolved }: {
  option: RecoveryOption;
  onChoose: () => void;
  busy: boolean;
  chosen: boolean;
  resolved: boolean;
}) {
  return (
    <Card className={`grid gap-3 p-4 md:grid-cols-[1fr_auto] md:items-center ${chosen ? "ring-2 ring-primary" : ""}`}>
      <div className="grid gap-1">
        <p className="flex items-center gap-2 font-medium">
          {option.type === "rebook_flight" ? <Plane className="size-4" /> : null}
          {option.title}
        </p>
        <p className="text-sm text-muted-foreground">{option.description}</p>
        {option.notes?.map((n) => (
          <p key={n} className="text-xs text-muted-foreground">
            • {n}
          </p>
        ))}
      </div>
      <div className="grid justify-items-end gap-2">
        {option.refund ? (
          <span className="font-semibold text-emerald-700 dark:text-emerald-400">Refund {formatMoney(option.refund)}</span>
        ) : (
          <span className="text-sm">{option.extra_cost.amount_minor ? formatMoney(option.extra_cost) : "No extra cost"}</span>
        )}
        {resolved ? (
          chosen ? <Badge>Chosen</Badge> : null
        ) : (
          <Button onClick={onChoose} disabled={busy} variant={option.type === "refund" ? "outline" : "default"}>
            {option.type === "refund" ? "Take the refund" : option.type === "keep" ? "Keep it" : "Choose this"}
          </Button>
        )}
      </div>
    </Card>
  );
}

export function RecoveryView() {
  const { id } = useParams<{ id: string }>();
  const { data: c, error, isPending } = useCase(id);
  const accept = useAccept(id);

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !c) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }
  const resolved = c.status !== "open";

  return (
    <div className="grid gap-5">
      <div>
        <p className="text-sm text-muted-foreground">Booking {c.booking_reference}</p>
        <h1 className="text-2xl font-semibold tracking-tight">{resolved ? "Sorted" : "Something changed with your trip"}</h1>
      </div>
      {resolved ? (
        <Alert>
          <CheckCircle2 className="text-emerald-600" />
          <AlertTitle>Resolved: {c.resolution}</AlertTitle>
          <AlertDescription>Your booking has been updated. Nothing else in your trip was changed.</AlertDescription>
        </Alert>
      ) : (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>{c.item_title}</AlertTitle>
          <AlertDescription>{c.summary}</AlertDescription>
        </Alert>
      )}
      <Card className="gap-2 p-4 text-sm">
        <p className="font-medium">The rest of your trip</p>
        {c.impact.map((line) => (
          <p key={line} className="text-muted-foreground">
            {line}
          </p>
        ))}
      </Card>
      <div className="grid gap-3">
        <h2 className="text-lg font-semibold">{resolved ? "Options offered" : "Your options"}</h2>
        {c.options.map((option) => (
          <OptionCard
            key={option.id}
            option={option}
            busy={accept.isPending}
            resolved={resolved}
            chosen={c.chosen_option_id === option.id}
            onChoose={() => accept.mutate(option.id, { onSuccess: () => toast.success("Done. Your booking is updated.") })}
          />
        ))}
        {accept.error ? (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertDescription>{errorMessage(accept.error)}</AlertDescription>
          </Alert>
        ) : null}
      </div>
      <div className="flex gap-2">
        <Button asChild variant="outline">
          <Link href={`/bookings/${c.booking_id}`}>Booking details</Link>
        </Button>
        <Button asChild variant="ghost">
          <Link href={`/trips/${c.trip_id}`}>View trip</Link>
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        TripMind never changes a booking on its own: you choose, then we re-check price and availability before
        anything is replaced.
      </p>
    </div>
  );
}
