"use client";

import { AlertCircle, BedDouble, CalendarDays, Plane, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toQuery } from "@/features/search/api";
import { addDays, formatDay, formatMoney } from "@/features/search/format";
import { errorMessage } from "@/lib/api/errors";

import { useTrip, useTrips, type Trip } from "../api";
import { StatusBadge } from "./booking-view";

const STATE: Record<Trip["state"], { label: string; className: string }> = {
  upcoming: { label: "Upcoming", className: "bg-primary/10 text-primary" },
  in_progress: { label: "On the trip", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  past: { label: "Completed", className: "bg-muted text-muted-foreground" },
  cancelled: { label: "Cancelled", className: "bg-muted text-muted-foreground" },
  pending: { label: "Awaiting payment", className: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
};

function TripState({ state }: { state: Trip["state"] }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATE[state].className}`}>{STATE[state].label}</span>;
}

function dates(trip: Trip) {
  if (!trip.starts_on) return null;
  return trip.ends_on && trip.ends_on !== trip.starts_on
    ? `${formatDay(trip.starts_on)} – ${formatDay(trip.ends_on)}`
    : formatDay(trip.starts_on);
}

export function TripsView() {
  const { data, error, isPending } = useTrips();
  if (isPending) return <Skeleton className="h-48 w-full" />;
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }
  if (!data.items.length) {
    return (
      <Card className="grid justify-items-center gap-3 p-10 text-center">
        <p className="font-medium">No trips yet</p>
        <p className="text-sm text-muted-foreground">Everything you book, flights and stays, lands here as one trip.</p>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/flights">Find a flight</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/stays">Find a stay</Link>
          </Button>
        </div>
      </Card>
    );
  }
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {data.items.map((trip) => (
        <Link key={trip.id} href={`/trips/${trip.id}`} className="group">
          <Card className="h-full gap-3 p-5 transition-colors group-hover:border-primary/40">
            <div className="flex items-start justify-between gap-2">
              <p className="text-lg font-semibold">{trip.title}</p>
              <TripState state={trip.state} />
            </div>
            <p className="flex items-center gap-1 text-sm text-muted-foreground">
              <CalendarDays className="size-4" /> {dates(trip) ?? "Dates not set"}
            </p>
            <div className="flex gap-3 text-sm">
              <span className={trip.has_flight ? "" : "text-muted-foreground line-through"}>
                <Plane className="mr-1 inline size-4" /> Flight
              </span>
              <span className={trip.has_stay ? "" : "text-muted-foreground line-through"}>
                <BedDouble className="mr-1 inline size-4" /> Stay
              </span>
            </div>
          </Card>
        </Link>
      ))}
    </div>
  );
}

export function TripDetailView() {
  const { id } = useParams<{ id: string }>();
  const { data: trip, error, isPending } = useTrip(id);
  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error || !trip) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  const active = trip.state !== "cancelled" && trip.state !== "past";
  const city = trip.destination_city_id;
  const addStay =
    active && trip.has_flight && !trip.has_stay && city && trip.starts_on
      ? `/stays?${toQuery({
          city,
          cityName: trip.destination_city_name ?? "",
          checkIn: trip.starts_on,
          checkOut: trip.ends_on && trip.ends_on > trip.starts_on ? trip.ends_on : addDays(trip.starts_on, 2),
          trip: trip.id,
        })}`
      : null;
  const addFlight =
    active && trip.has_stay && !trip.has_flight && city && trip.starts_on
      ? `/flights?${toQuery({ to: city, toLabel: trip.destination_city_name ?? "", depart: trip.starts_on, trip: trip.id })}`
      : null;

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{trip.title}</h1>
        <TripState state={trip.state} />
      </div>
      <p className="flex items-center gap-1 text-muted-foreground">
        <CalendarDays className="size-4" /> {dates(trip) ?? "Dates not set"}
      </p>

      {addStay || addFlight ? (
        <Card className="flex flex-wrap items-center justify-between gap-3 border-primary/30 bg-primary/5 p-5">
          <div>
            <p className="font-medium">{addStay ? `Need somewhere to stay in ${trip.destination_city_name}?` : "Need a flight for this stay?"}</p>
            <p className="text-sm text-muted-foreground">It joins this trip, with your dates already filled in.</p>
          </div>
          <Button asChild>
            <Link href={(addStay ?? addFlight)!}>
              <Plus /> {addStay ? "Add a stay" : "Add a flight"}
            </Link>
          </Button>
        </Card>
      ) : null}

      {trip.bookings.map((booking) => (
        <Card key={booking.id}>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              Booking {booking.reference} <StatusBadge status={booking.status} />
            </CardTitle>
            <Button asChild variant="outline" size="sm">
              <Link href={`/bookings/${booking.id}`}>Manage</Link>
            </Button>
          </CardHeader>
          <CardContent className="grid gap-3">
            {booking.items.map((item) => (
              <div key={item.id} className="flex flex-wrap items-start justify-between gap-2 text-sm">
                <div className="flex gap-2">
                  {item.kind === "flight" ? <Plane className="mt-0.5 size-4" /> : <BedDouble className="mt-0.5 size-4" />}
                  <div>
                    <p className="font-medium">
                      {item.title} <StatusBadge status={item.status} />
                    </p>
                    <p className="text-muted-foreground">{item.subtitle}</p>
                  </div>
                </div>
                <span className="tabular-nums">{formatMoney(item.price)}</span>
              </div>
            ))}
            <div className="flex justify-between border-t pt-2 text-sm font-semibold">
              <span>Total paid or due</span>
              <span className="tabular-nums">{formatMoney(booking.total)}</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
