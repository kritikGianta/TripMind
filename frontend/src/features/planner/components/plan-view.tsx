"use client";

import { AlertCircle, BedDouble, Bookmark, BookmarkCheck, ChevronDown, Info, Plane, ShieldAlert, ShieldCheck, ShieldQuestion, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toQuery } from "@/features/search/api";
import { Stars } from "@/features/search/components/hotel-results";
import { clockTime, formatDay, formatDuration, formatMoney } from "@/features/search/format";
import { errorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

import { useOptionState, usePlan, usePlans, type Bundle, type Plan } from "../api";

const LEVEL = {
  high: { icon: ShieldCheck, label: "High confidence", className: "text-emerald-700 bg-emerald-500/10 dark:text-emerald-300" },
  medium: { icon: ShieldQuestion, label: "Medium confidence", className: "text-amber-700 bg-amber-500/10 dark:text-amber-300" },
  low: { icon: ShieldAlert, label: "Low confidence", className: "text-destructive bg-destructive/10" },
} as const;

const CHECK_STYLE: Record<string, string> = {
  ok: "bg-emerald-500",
  info: "bg-sky-500",
  warn: "bg-amber-500",
  risk: "bg-destructive",
};

const FACTORS = [
  { key: "price", label: "Price" },
  { key: "time", label: "Journey time" },
  { key: "stay", label: "Stay" },
  { key: "convenience", label: "Convenience" },
] as const;

function FlightLine({ label, offer }: { label: string; offer: Bundle["outbound"] }) {
  const first = offer.legs[0];
  const last = offer.legs[offer.legs.length - 1];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      <Plane className="size-4 text-muted-foreground" />
      <span className="w-14 text-xs text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">
        {formatDay(first.departure_local)} {clockTime(first.departure_local)} {first.origin.code} → {clockTime(last.arrival_local)}{" "}
        {last.destination.code}
      </span>
      <span className="text-muted-foreground">
        {formatDuration(offer.duration_minutes)} · {offer.stops === 0 ? "direct" : `${offer.stops} stop`} ·{" "}
        {offer.legs.map((l) => l.flight_number).join(" + ")}
      </span>
    </div>
  );
}

function BundleCard({ plan, bundle }: { plan: Plan; bundle: Bundle }) {
  const [open, setOpen] = useState(bundle.rank === 1);
  const mark = useOptionState(plan.id);
  const level = LEVEL[bundle.confidence.level];
  const LevelIcon = level.icon;
  const checkout = `/checkout?${toQuery({
    flight: [bundle.outbound.id, bundle.inbound.id],
    adults: plan.request.adults,
    room: bundle.hotel.cheapest_room.room_type_id,
    checkIn: bundle.stay.check_in,
    checkOut: bundle.stay.check_out,
    rooms: bundle.stay.rooms,
    guests: bundle.stay.guests,
  })}`;

  return (
    <Card className={cn("gap-0 p-0", bundle.state === "saved" && "ring-2 ring-primary")}>
      <div className="grid gap-4 p-5 md:grid-cols-[3rem_1fr_auto]">
        <div className="flex size-10 items-center justify-center rounded-full bg-primary/10 font-semibold text-primary">
          #{bundle.rank}
        </div>
        <div className="grid gap-2">
          <FlightLine label="Out" offer={bundle.outbound} />
          <FlightLine label="Back" offer={bundle.inbound} />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <BedDouble className="size-4 text-muted-foreground" />
            <span className="w-14 text-xs text-muted-foreground">Stay</span>
            <span className="font-medium">{bundle.hotel.name}</span>
            <Stars count={bundle.hotel.star_rating} />
            <span className="text-muted-foreground">
              {bundle.hotel.guest_rating ? `${bundle.hotel.guest_rating.toFixed(1)}/10 · ` : ""}
              {bundle.hotel.cheapest_room.name} · {bundle.stay.nights} night{bundle.stay.nights > 1 ? "s" : ""}
            </span>
          </div>
          <span className={cn("mt-1 inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", level.className)}>
            <LevelIcon className="size-3.5" /> {level.label}: {bundle.confidence.summary}
          </span>
        </div>
        <div className="grid content-start justify-items-end gap-2">
          <span className="text-2xl font-semibold tabular-nums">≈ {formatMoney(bundle.total)}</span>
          <span className="text-xs text-muted-foreground">
            whole trip, {plan.request.adults} adult{plan.request.adults > 1 ? "s" : ""}
            {bundle.complete ? "" : ", before taxes and fees"}
          </span>
          <Button asChild>
            <Link href={checkout}>Book this trip</Link>
          </Button>
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" disabled={mark.isPending}
              onClick={() => mark.mutate({ optionId: bundle.id, state: bundle.state === "saved" ? "none" : "saved" })}>
              {bundle.state === "saved" ? <BookmarkCheck /> : <Bookmark />} {bundle.state === "saved" ? "Saved" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" disabled={mark.isPending}
              onClick={() => mark.mutate({ optionId: bundle.id, state: "dismissed" })}>
              <X /> Not for me
            </Button>
          </div>
        </div>
      </div>

      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="flex items-center gap-1 border-t px-5 py-2 text-left text-sm text-muted-foreground hover:text-foreground">
        Why this rank, and what to check <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="grid gap-6 border-t bg-muted/30 p-5 md:grid-cols-2">
          <div className="grid content-start gap-3">
            <p className="text-sm font-medium">Why #{bundle.rank}</p>
            <ul className="grid list-disc gap-1 pl-5 text-sm">
              {bundle.explanation.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <div className="grid gap-1.5">
              {FACTORS.map(({ key, label }) => (
                <div key={key} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-2 text-xs">
                  <span className="text-muted-foreground">
                    {label} <span className="opacity-70">×{plan.weights[key]?.toFixed(2)}</span>
                  </span>
                  <span className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <span className="block h-full rounded-full bg-primary" style={{ width: `${bundle.scores[key] * 100}%` }} />
                  </span>
                  <span className="text-right tabular-nums">{bundle.scores[key].toFixed(2)}</span>
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                Score {bundle.scores.total.toFixed(3)} = Σ weight × factor. Weights come from config/ranking.yaml.
              </p>
            </div>
          </div>
          <div className="grid content-start gap-2">
            <p className="text-sm font-medium">Journey Confidence Report</p>
            <ul className="grid gap-2 text-sm">
              {bundle.confidence.checks.map((check) => (
                <li key={check.name + check.message} className="grid grid-cols-[0.5rem_1fr] gap-2">
                  <span className={cn("mt-1.5 size-2 rounded-full", CHECK_STYLE[check.status])} aria-label={check.status} />
                  <span>
                    <span className="font-medium">{check.name}.</span> {check.message}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

export function PlanView() {
  const { id } = useParams<{ id: string }>();
  const { data: plan, error, isPending } = usePlan(id);
  const mark = useOptionState(id);
  const [showDismissed, setShowDismissed] = useState(false);

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !plan) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  const visible = plan.options.filter((o) => o.state !== "dismissed");
  const dismissed = plan.options.filter((o) => o.state === "dismissed");
  const saved = visible.filter((o) => o.state === "saved");
  const ordered = [...saved, ...visible.filter((o) => o.state !== "saved")];

  return (
    <div className="grid gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{plan.title}</h1>
        <p className="text-sm text-muted-foreground">
          {plan.request.adults} adult{plan.request.adults > 1 ? "s" : ""} · priority: {plan.request.priority} ·{" "}
          {plan.options.length} complete trips ranked · {saved.length} saved
        </p>
      </div>
      {plan.notices.map((n) => (
        <Alert key={n}>
          <Info />
          <AlertDescription>{n}</AlertDescription>
        </Alert>
      ))}
      {ordered.map((bundle) => (
        <BundleCard key={bundle.id} plan={plan} bundle={bundle} />
      ))}
      {dismissed.length ? (
        <div className="grid gap-2">
          <Button variant="ghost" size="sm" className="w-fit" onClick={() => setShowDismissed((v) => !v)}>
            {showDismissed ? "Hide" : "Show"} {dismissed.length} dismissed option{dismissed.length > 1 ? "s" : ""}
          </Button>
          {showDismissed
            ? dismissed.map((b) => (
                <Card key={b.id} className="flex flex-row flex-wrap items-center justify-between gap-2 p-4 text-sm text-muted-foreground">
                  <span>
                    #{b.rank} · {b.hotel.name} · ≈ {formatMoney(b.total)}
                  </span>
                  <Button size="sm" variant="outline" onClick={() => mark.mutate({ optionId: b.id, state: "none" })}>
                    Restore
                  </Button>
                </Card>
              ))
            : null}
        </div>
      ) : null}
      <Badge variant="outline" className="w-fit">
        Ranking and checks are computed from the data; no AI is used on this page.
      </Badge>
    </div>
  );
}

export function PlansList() {
  const { data } = usePlans();
  if (!data?.items.length) return null;
  return (
    <div className="grid gap-2">
      <h2 className="text-lg font-semibold">Your plans</h2>
      <div className="grid gap-2 md:grid-cols-2">
        {data.items.map((p) => (
          <Link key={p.id} href={`/plans/${p.id}`}>
            <Card className="gap-1 p-4 transition-colors hover:border-primary/40">
              <p className="font-medium">{p.title}</p>
              <p className="text-xs text-muted-foreground">
                {p.options} options · {p.saved} saved · {p.priority}
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
