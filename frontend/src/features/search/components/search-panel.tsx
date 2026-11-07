"use client";

import { ArrowLeftRight, BedDouble, Plane, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { toQuery, useDataset } from "../api";
import { addDays, CABIN_LABELS, todayIso } from "../format";
import { LocationPicker, type PickedLocation } from "./location-picker";

export type FlightFormValues = {
  from: PickedLocation | null;
  to: PickedLocation | null;
  depart: string;
  ret: string;
  adults: number;
  cabin: string;
};

export type StayFormValues = {
  city: PickedLocation | null;
  checkIn: string;
  checkOut: string;
  guests: number;
  rooms: number;
};

/** First searchable date: tomorrow, or the start of the dataset's travel window if later. */
function useDefaultDate() {
  const { data } = useDataset();
  const tomorrow = addDays(todayIso(), 1);
  const first = data?.travel_window?.first_departure;
  return { start: first && first > tomorrow ? first : tomorrow, window: data?.travel_window ?? null };
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}

function FlightForm({ initial }: { initial?: Partial<FlightFormValues> }) {
  const router = useRouter();
  const { start, window } = useDefaultDate();
  const [from, setFrom] = useState<PickedLocation | null>(initial?.from ?? null);
  const [to, setTo] = useState<PickedLocation | null>(initial?.to ?? null);
  const [tripType, setTripType] = useState<"return" | "oneway">(initial && !initial.ret ? "oneway" : "return");
  const [depart, setDepart] = useState(initial?.depart ?? "");
  const [ret, setRet] = useState(initial?.ret ?? "");
  const [adults, setAdults] = useState(initial?.adults ?? 1);
  const [cabin, setCabin] = useState(initial?.cabin ?? "economy");
  const [error, setError] = useState<string | null>(null);

  const departValue = depart || start;
  const returnValue = ret || addDays(departValue, 4);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!from || !to) return setError("Choose where you're flying from and to.");
    if (from.value === to.value) return setError("Origin and destination must be different.");
    if (tripType === "return" && returnValue < departValue) return setError("Return must be on or after departure.");
    setError(null);
    router.push(
      `/flights?${toQuery({
        from: from.value,
        fromLabel: from.label,
        to: to.value,
        toLabel: to.label,
        depart: departValue,
        return: tripType === "return" ? returnValue : undefined,
        adults,
        cabin,
      })}`,
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-4" noValidate>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Select value={tripType} onValueChange={(v) => setTripType(v as "return" | "oneway")}>
          <SelectTrigger className="h-8 w-32" aria-label="Trip type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="return">Return</SelectItem>
            <SelectItem value="oneway">One way</SelectItem>
          </SelectContent>
        </Select>
        <Select value={String(adults)} onValueChange={(v) => setAdults(Number(v))}>
          <SelectTrigger className="h-8 w-32" aria-label="Adults">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Array.from({ length: 9 }, (_, i) => i + 1).map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} adult{n > 1 ? "s" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={cabin} onValueChange={setCabin}>
          <SelectTrigger className="h-8 w-40" aria-label="Cabin">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {["economy", "business"].map((c) => (
              <SelectItem key={c} value={c}>
                {CABIN_LABELS[c]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_10rem_10rem_auto] md:items-end">
        <Field label="From" htmlFor="flight-from">
          <LocationPicker id="flight-from" kind="airport" value={from} onChange={setFrom} placeholder="Leaving from" />
        </Field>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="hidden md:inline-flex"
          aria-label="Swap origin and destination"
          onClick={() => {
            setFrom(to);
            setTo(from);
          }}
        >
          <ArrowLeftRight />
        </Button>
        <Field label="To" htmlFor="flight-to">
          <LocationPicker id="flight-to" kind="airport" value={to} onChange={setTo} placeholder="Going to" />
        </Field>
        <Field label="Depart" htmlFor="flight-depart">
          <Input
            id="flight-depart"
            type="date"
            className="h-11"
            value={departValue}
            min={todayIso()}
            max={window?.last_departure}
            onChange={(e) => setDepart(e.target.value)}
          />
        </Field>
        <Field label="Return" htmlFor="flight-return">
          <Input
            id="flight-return"
            type="date"
            className="h-11"
            value={tripType === "return" ? returnValue : ""}
            disabled={tripType === "oneway"}
            min={departValue}
            max={window?.last_departure}
            onChange={(e) => setRet(e.target.value)}
          />
        </Field>
        <Button type="submit" size="lg" className="h-11">
          <Search /> Search
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  );
}

function StayForm({ initial }: { initial?: Partial<StayFormValues> }) {
  const router = useRouter();
  const { start } = useDefaultDate();
  const [city, setCity] = useState<PickedLocation | null>(initial?.city ?? null);
  const [checkIn, setCheckIn] = useState(initial?.checkIn ?? "");
  const [checkOut, setCheckOut] = useState(initial?.checkOut ?? "");
  const [guests, setGuests] = useState(initial?.guests ?? 2);
  const [rooms, setRooms] = useState(initial?.rooms ?? 1);
  const [error, setError] = useState<string | null>(null);

  const inValue = checkIn || start;
  const outValue = checkOut || addDays(inValue, 3);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!city) return setError("Choose a city.");
    if (outValue <= inValue) return setError("Check-out must be after check-in.");
    if (rooms > guests) return setError("Each room needs at least one guest.");
    setError(null);
    router.push(
      `/stays?${toQuery({ city: city.value, cityName: city.label, checkIn: inValue, checkOut: outValue, guests, rooms })}`,
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-4" noValidate>
      <div className="grid gap-3 md:grid-cols-[1fr_10rem_10rem_8rem_8rem_auto] md:items-end">
        <Field label="Destination" htmlFor="stay-city">
          <LocationPicker id="stay-city" kind="city" value={city} onChange={setCity} placeholder="Where are you going?" />
        </Field>
        <Field label="Check-in" htmlFor="stay-in">
          <Input
            id="stay-in"
            type="date"
            className="h-11"
            value={inValue}
            min={todayIso()}
            onChange={(e) => setCheckIn(e.target.value)}
          />
        </Field>
        <Field label="Check-out" htmlFor="stay-out">
          <Input
            id="stay-out"
            type="date"
            className="h-11"
            value={outValue}
            min={addDays(inValue, 1)}
            onChange={(e) => setCheckOut(e.target.value)}
          />
        </Field>
        <Field label="Guests" htmlFor="stay-guests">
          <Select value={String(guests)} onValueChange={(v) => setGuests(Number(v))}>
            <SelectTrigger id="stay-guests" className="!h-11 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: 16 }, (_, i) => i + 1).map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n} guest{n > 1 ? "s" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Rooms" htmlFor="stay-rooms">
          <Select value={String(rooms)} onValueChange={(v) => setRooms(Number(v))}>
            <SelectTrigger id="stay-rooms" className="!h-11 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n} room{n > 1 ? "s" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Button type="submit" size="lg" className="h-11">
          <Search /> Search
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </form>
  );
}

export function SearchPanel({
  defaultTab = "flights",
  flight,
  stay,
}: {
  defaultTab?: "flights" | "stays";
  flight?: Partial<FlightFormValues>;
  stay?: Partial<StayFormValues>;
}) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm md:p-5">
      <Tabs defaultValue={defaultTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="flights">
            <Plane /> Flights
          </TabsTrigger>
          <TabsTrigger value="stays">
            <BedDouble /> Stays
          </TabsTrigger>
        </TabsList>
        <TabsContent value="flights">
          <FlightForm initial={flight} />
        </TabsContent>
        <TabsContent value="stays">
          <StayForm initial={stay} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
