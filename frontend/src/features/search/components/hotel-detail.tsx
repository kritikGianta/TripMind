"use client";

import { AlertCircle, ArrowLeft, BedDouble, Clock, MapPin, Users } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { toQuery, useHotel } from "../api";
import { BOARD_LABELS, formatDay, formatMoney } from "../format";
import { RatingBadge, Stars } from "./hotel-results";
import { HotelReviews, SaveStayButton, WatchPriceButton } from "./stay-extras";
import { PriceBreakdown } from "./price-breakdown";

const AMENITY_LABELS: Record<string, string> = {
  wifi: "Wi-Fi",
  air_conditioning: "Air conditioning",
  restaurant: "Restaurant",
  pool: "Pool",
  gym: "Gym",
  spa: "Spa",
  bar: "Bar",
  room_service: "Room service",
  parking: "Parking",
  airport_shuttle: "Airport shuttle",
  wheelchair_accessible: "Wheelchair accessible",
  pet_friendly: "Pet friendly",
  family_rooms: "Family rooms",
  beach_access: "Beach access",
  ev_charging: "EV charging",
  business_centre: "Business centre",
  laundry: "Laundry",
};

export function HotelDetailView({ id }: { id: string }) {
  const params = useSearchParams();
  const checkIn = params.get("checkIn");
  const checkOut = params.get("checkOut");
  const guests = params.get("guests") ?? "2";
  const rooms = params.get("rooms") ?? "1";
  const trip = params.get("trip");
  const query = toQuery({ check_in: checkIn, check_out: checkOut, guests, rooms });
  const { data, error, isPending } = useHotel(id, query);

  if (isPending) {
    return (
      <div className="mx-auto grid w-full max-w-6xl gap-4 px-4 py-8">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-8">
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{errorMessage(error)}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const backQuery = toQuery({ city: data.city.id, cityName: data.city.name, checkIn, checkOut, guests, rooms, trip });

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-8">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link href={`/stays?${backQuery}`}>
          <ArrowLeft /> All stays in {data.city.name}
        </Link>
      </Button>

      <header className="grid gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">{data.name}</h1>
          <Stars count={data.star_rating} />
          {data.origin === "synthetic" ? <Badge variant="outline">Demo data</Badge> : null}
          <span className="flex flex-wrap gap-2 sm:ml-auto">
            <SaveStayButton hotelId={data.id} />
            {data.stay ? (
              <WatchPriceButton
                watch={{ kind: "hotel", hotel_id: data.id, check_in: data.stay.check_in, check_out: data.stay.check_out, guests: data.stay.guests, rooms: data.stay.rooms }}
              />
            ) : null}
          </span>
        </div>
        <p className="flex items-center gap-1 text-muted-foreground">
          <MapPin className="size-4" aria-hidden />
          {data.address ?? data.city.name}
          {data.distance_km !== null && data.distance_km !== undefined ? ` · ${data.distance_km} km from centre` : ""}
        </p>
        <RatingBadge rating={data.guest_rating} reviews={data.review_count} />
      </header>

      <div className="grid gap-4 md:grid-cols-[2fr_1fr]">
        <Card className="grid gap-3 p-5">
          <h2 className="font-semibold">About this stay</h2>
          <p className="text-sm text-muted-foreground">{data.description ?? "No description in the supplied data."}</p>
          <div className="flex flex-wrap gap-1.5">
            {data.amenities.map((a) => (
              <Badge key={a} variant="secondary">
                {AMENITY_LABELS[a] ?? a.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
        </Card>
        <Card className="grid content-start gap-3 p-5 text-sm">
          <h2 className="font-semibold">Your stay</h2>
          {data.stay ? (
            <>
              <p>
                {formatDay(data.stay.check_in)} – {formatDay(data.stay.check_out)} · {data.stay.nights} night
                {data.stay.nights > 1 ? "s" : ""}
              </p>
              <p className="flex items-center gap-1 text-muted-foreground">
                <Users className="size-4" /> {data.stay.guests} guests · {data.stay.rooms} room{data.stay.rooms > 1 ? "s" : ""}
              </p>
            </>
          ) : (
            <p className="text-muted-foreground">Choose dates on the search page to see prices.</p>
          )}
          <p className="flex items-center gap-1 text-muted-foreground">
            <Clock className="size-4" /> Check-in {data.check_in_time ?? "—"} · Check-out {data.check_out_time ?? "—"}
          </p>
        </Card>
      </div>

      <section className="grid gap-3">
        <h2 className="text-xl font-semibold">Rooms</h2>
        {data.rooms.map((room) => (
          <Card key={room.room_type_id} className="grid gap-4 p-4 md:grid-cols-[1fr_auto] md:items-center">
            <div className="grid gap-1.5">
              <div className="flex items-center gap-2 font-medium">
                <BedDouble className="size-4 text-muted-foreground" aria-hidden /> {room.name}
              </div>
              <p className="text-sm text-muted-foreground">
                Sleeps {room.max_occupancy}
                {room.bed_type ? ` · ${room.bed_type}` : ""}
                {room.nightly_rate ? ` · ${formatMoney(room.nightly_rate)} per night` : ""}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {room.refundable === true ? (
                  <Badge variant="outline" className="text-emerald-700 dark:text-emerald-400">Free cancellation</Badge>
                ) : room.refundable === false ? (
                  <Badge variant="outline">Non-refundable</Badge>
                ) : null}
                {room.board ? <Badge variant="outline">{BOARD_LABELS[room.board] ?? room.board}</Badge> : null}
                {!room.fits_party ? <Badge variant="outline">Doesn&apos;t fit your party</Badge> : null}
              </div>
            </div>
            <div className="flex items-center justify-between gap-4 md:justify-end">
              {room.price ? <PriceBreakdown ledger={room.price} caption="for your stay" /> : null}
              {room.fits_party && room.nightly_rate && data.stay ? (
                <Button asChild>
                  <Link
                    href={`/checkout?${toQuery({ room: room.room_type_id, checkIn, checkOut, rooms, guests, trip })}`}
                  >
                    Reserve
                  </Link>
                </Button>
              ) : (
                <Button disabled>{room.fits_party ? "Not bookable" : "Too small"}</Button>
              )}
            </div>
          </Card>
        ))}
      </section>
      <HotelReviews hotelId={data.id} />
    </div>
  );
}
