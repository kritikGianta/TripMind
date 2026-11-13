"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BedDouble, Bus, Download, Landmark, Plane, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { FormError } from "@/features/auth/components/form-error";
import { apiFetch, API_BASE, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { useQuery } from "@/lib/api/use-query";

type Options = Schemas["OptionsOut"];
type Build = Schemas["BuildOut"];
type Package = Schemas["PackageOut"];
type Alternative = Schemas["AlternativeOut"];
type Item = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;
const LABELS: Record<string, string> = { cheapest: "Cheapest", fastest: "Fastest", best_rated: "Best rated" };
const ICONS = { flight: Plane, hotel: BedDouble, transfer: Bus, attraction: Landmark } as const;
const dayName = (iso: string) =>
  new Date(`${iso.slice(0, 10)}T00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });

// ── M1: the request form ─────────────────────────────────────────────────────────────────────

export function HolidayPlanner() {
  const router = useRouter();
  const options = useQuery({ queryKey: ["holiday", "options"], queryFn: () => apiFetch<Options>("/holiday/options") });
  const [form, setForm] = useState({
    departure_airport: "BLR",
    country: "Japan",
    start_date: "2027-04-10",
    nights: "6",
    adults: "2",
    child_ages: "6",
    budget_inr: "350000",
  });
  const [problem, setProblem] = useState<string | null>(null);
  const build = useMutation({
    mutationFn: (body: Schemas["HolidayRequestIn"]) => apiFetch<Build>("/holiday/packages", { method: "POST", body }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const ages = form.child_ages.trim() ? form.child_ages.split(",").map((a) => Number(a.trim())) : [];
    const nights = Number(form.nights);
    const adults = Number(form.adults);
    const budget = Number(form.budget_inr);
    // Clear messages for values that are not valid (M1); the server checks every rule again.
    if (!form.start_date) return setProblem("Choose the holiday start date.");
    if (!Number.isInteger(nights) || nights < 3 || nights > 10) return setProblem("A trip is 3 to 10 nights.");
    if (!Number.isInteger(adults) || adults < 1) return setProblem("At least one adult must travel.");
    if (ages.some((a) => !Number.isInteger(a) || a < 0 || a > 17)) return setProblem("Children's ages are whole numbers from 0 to 17, separated by commas.");
    if (!Number.isFinite(budget) || budget <= 0) return setProblem("Enter a budget in rupees.");
    setProblem(null);
    build.mutate({ ...form, nights, adults, child_ages: ages, budget_inr: budget });
  }

  const set = (key: keyof typeof form) => (value: string) => setForm({ ...form, [key]: value });
  const result = build.data;

  // Quick request (S1): the backend reads the sentence with rules (no AI) and fills the form.
  const [sentence, setSentence] = useState("");
  const quick = useMutation({
    mutationFn: (text: string) => apiFetch<Schemas["QuickOut"]>("/holiday/parse", { method: "POST", body: { text } }),
    onSuccess: (data) => {
      const f = data.fields as Record<string, unknown>;
      setForm((current) => ({
        ...current,
        ...Object.fromEntries(
          Object.entries(f).map(([key, value]) => [key, Array.isArray(value) ? value.join(", ") : String(value)]),
        ),
      }));
    },
  });

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Book my holiday</CardTitle>
          <CardDescription>
            Tell us the trip; TripMind chooses the cities and builds flights, hotels, transfers and attractions.
            {options.data ? ` Travel dates: ${dayName(options.data.first_night)} to ${dayName(options.data.last_departure)}.` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <form
            className="grid gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (sentence.trim().length >= 3) quick.mutate(sentence.trim());
            }}
          >
            <Label htmlFor="quick">Quick request: type it in your own words</Label>
            <div className="flex gap-2">
              <Input
                id="quick"
                placeholder="2 adults and a 6 year old from Bengaluru to Japan on 10 April for 6 nights under 3.5 lakh"
                value={sentence}
                onChange={(e) => setSentence(e.target.value)}
              />
              <Button type="submit" variant="outline" disabled={quick.isPending}>
                Fill the form
              </Button>
            </div>
            {quick.data ? (
              <p className="text-sm text-muted-foreground">
                {quick.data.understood.length ? `Understood: ${quick.data.understood.join(" · ")}.` : "Nothing understood yet."}
                {quick.data.missing.length ? ` Please check: ${quick.data.missing.join(", ")}.` : ""}
              </p>
            ) : null}
            {quick.data?.notes?.length ? (
              <p className="text-sm text-amber-700 dark:text-amber-300">{quick.data.notes.join(" ")}</p>
            ) : null}
            <FormError error={quick.error} />
          </form>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-4" noValidate>
            <div className="grid gap-1.5">
              <Label>Departure city</Label>
              <Select value={form.departure_airport} onValueChange={set("departure_airport")}>
                <SelectTrigger aria-label="Departure city">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(options.data?.departure_cities ?? []).map((d) => (
                    <SelectItem key={d.airport} value={d.airport}>
                      {d.city} ({d.airport})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Destination country</Label>
              <Select value={form.country} onValueChange={set("country")}>
                <SelectTrigger aria-label="Destination country">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(options.data?.countries ?? []).map((c) => (
                    <SelectItem key={c.name as string} value={c.name as string}>
                      {c.name as string} · {(c.cities as string[]).join(", ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Field id="start" label="Holiday start date (you land)" type="date" value={form.start_date} onChange={set("start_date")} min={options.data?.first_night} max={options.data?.last_departure} />
            <Field id="nights" label="Nights (3-10)" type="number" value={form.nights} onChange={set("nights")} />
            <Field id="adults" label="Adults" type="number" value={form.adults} onChange={set("adults")} />
            <Field id="ages" label="Children's ages (e.g. 6, 9)" value={form.child_ages} onChange={set("child_ages")} />
            <Field id="budget" label="Budget for everything (₹)" type="number" value={form.budget_inr} onChange={set("budget_inr")} />
            <div className="flex items-end">
              <Button type="submit" size="lg" className="w-full" disabled={build.isPending}>
                <Search /> {build.isPending ? "Building…" : "Build my holiday"}
              </Button>
            </div>
          </form>
          {problem ? <p className="mt-3 text-sm text-destructive">{problem}</p> : null}
          <FormError error={build.error} />
        </CardContent>
      </Card>

      {result ? (
        <div className="grid gap-4">
          {result.message ? (
            <Card className="border-amber-500/50">
              <CardContent className="grid gap-1 pt-6 text-sm">
                <p className="font-semibold">{result.message}</p>
                {(result.reasons ?? []).map((r) => (
                  <p key={r} className="text-muted-foreground">
                    {r}
                  </p>
                ))}
                {result.cheapest_total_inr ? <p>Cheapest possible total: {inr(result.cheapest_total_inr)}</p> : null}
                {result.suggestion ? <p className="text-muted-foreground">{result.suggestion}</p> : null}
              </CardContent>
            </Card>
          ) : null}
          <div className="grid gap-4 md:grid-cols-3">
            {result.packages.map((p) => (
              <Card key={p.id} className="flex flex-col">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {LABELS[p.label] ?? p.label}
                    {p.left_inr >= 0 ? <Badge variant="secondary">Within budget</Badge> : <Badge variant="destructive">Over budget</Badge>}
                  </CardTitle>
                  <CardDescription>{p.cities.map((c) => `${c.city as string} ${c.nights as number}n`).join(" → ")}</CardDescription>
                </CardHeader>
                <CardContent className="grid flex-1 content-between gap-3 text-sm">
                  <div className="grid gap-1">
                    <p className="text-2xl font-semibold">{inr(p.total_inr)}</p>
                    <p className="text-muted-foreground">
                      {p.left_inr >= 0 ? `${inr(p.left_inr)} left of ${inr(p.budget_inr)}` : `${inr(-p.left_inr)} over ${inr(p.budget_inr)}`}
                    </p>
                    <p className="text-muted-foreground">
                      {Math.round(p.travel_minutes / 60)} h travelling · hotels average {p.average_stars}★
                    </p>
                  </div>
                  <Button onClick={() => router.push(`/holiday/packages/${p.id}`)}>View and choose</Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Field(props: { id: string; label: string; value: string; onChange: (v: string) => void; type?: string; min?: string; max?: string }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={props.id}>{props.label}</Label>
      <Input id={props.id} type={props.type ?? "text"} min={props.min} max={props.max} value={props.value} onChange={(e) => props.onChange(e.target.value)} />
    </div>
  );
}

// ── M4, M5: day-by-day plan and totals ───────────────────────────────────────────────────────

function DayPlan({ pkg, onRemove }: { pkg: Package; onRemove?: (itemId: string) => void }) {
  const days = new Map<string, Item[]>();
  for (const item of pkg.items as Item[]) {
    const day = String(item.start).slice(0, 10);
    days.set(day, [...(days.get(day) ?? []), item]);
  }
  return (
    <div className="grid gap-3">
      {[...days.entries()].map(([day, items]) => (
        <Card key={day}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{dayName(day)}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            {items.map((item) => {
              const Icon = ICONS[item.type as keyof typeof ICONS] ?? Landmark;
              const time = item.type === "hotel" ? `Check in · ${item.details.nights} nights` : `${String(item.start).slice(11, 16)}–${String(item.end ?? "").slice(11, 16)}`;
              return (
                <div key={item.item_id} className="flex items-start justify-between gap-3 border-t pt-2 first:border-0 first:pt-0">
                  <div className="flex gap-2">
                    <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="text-muted-foreground">
                        {time}
                        {item.type === "hotel" ? ` · ${item.quantity} × ${item.details.room_name} · ${item.details.stars}★ · ${item.details.area}` : ""}
                        {item.type === "flight" ? ` · ${item.details.stops ? "1 stop" : "direct"} · ${item.quantity} seats` : ""}
                      </p>
                      {(item.warnings as string[]).map((w) => (
                        <p key={w} className="text-amber-700 dark:text-amber-300">
                          {w}
                        </p>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="tabular-nums">{inr(item.price_inr)}</span>
                    {onRemove && item.type === "attraction" && pkg.status === "PLANNED" ? (
                      <Button size="icon" variant="ghost" aria-label={`Remove ${item.name}`} onClick={() => onRemove(item.item_id)}>
                        <Trash2 />
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Totals({ pkg }: { pkg: Package }) {
  return (
    <Card>
      <CardContent className="grid gap-1 pt-6 text-sm">
        <div className="flex justify-between text-lg font-semibold">
          <span>Total</span>
          <span>{inr(pkg.total_inr)}</span>
        </div>
        <div className="flex justify-between font-medium">
          <span>Budget</span>
          <span>{inr(pkg.budget_inr)}</span>
        </div>
        <div className={`flex justify-between font-medium ${pkg.left_inr < 0 ? "text-destructive" : ""}`}>
          <span>{pkg.left_inr >= 0 ? "Left" : "Over budget by"}</span>
          <span>{inr(Math.abs(pkg.left_inr))}</span>
        </div>
        <a className="mt-2 inline-flex items-center gap-1 text-sm font-medium underline" href={`${API_BASE}/holiday/packages/${pkg.id}/export`}>
          <Download className="size-4" /> Download JSON
        </a>
        {pkg.problems.length ? <p className="text-destructive">Broken rules: {pkg.problems.join(" ")}</p> : null}
      </CardContent>
    </Card>
  );
}

// ── M6, M7: change the package, then confirm ─────────────────────────────────────────────────

export function PackageView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const key = ["holiday", "package", id];
  const pkg = useQuery({ queryKey: key, queryFn: () => apiFetch<Package>(`/holiday/packages/${id}`) });
  const change = useMutation({
    mutationFn: (body: Schemas["ChangeIn"]) => apiFetch<Package>(`/holiday/packages/${id}/changes`, { method: "POST", body }),
    onSuccess: (data) => {
      client.setQueryData(key, data);
      toast.success("Package updated. Every rule was checked again.");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const confirm = useMutation({
    mutationFn: () => apiFetch<Package>(`/holiday/packages/${id}/confirm`, { method: "POST" }),
    onSuccess: (data) => {
      void client.invalidateQueries({ queryKey: ["notifications"] });
      router.push(`/holiday/reservation?ref=${data.reference}`);
    },
  });
  if (pkg.isPending) return <Skeleton className="h-96 w-full" />;
  if (!pkg.data) return <FormError error={pkg.error} />;
  const data = pkg.data;
  const editable = data.status === "PLANNED";
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="grid content-start gap-4">
        <h1>
          {LABELS[data.label] ?? data.label} holiday in {String(data.request.country)}
        </h1>
        <p className="text-muted-foreground">{data.cities.map((c) => `${c.city as string} (${c.nights as number} nights)`).join(" → ")}</p>
        <DayPlan pkg={data} onRemove={editable ? (item_id) => change.mutate({ action: "remove_attraction", item_id }) : undefined} />
      </div>
      <div className="grid content-start gap-4">
        <Totals pkg={data} />
        {editable ? (
          <>
            {data.cities.map((c) => (
              <ChangeHotel key={c.city as string} id={id} city={c.city as string} onPick={(a) => change.mutate({ action: "hotel", city: c.city as string, hotel_id: a.catalog_id, room_id: a.room_id })} />
            ))}
            {(["arrival", "return"] as const).map((leg) => (
              <ChangeFlight key={leg} id={id} leg={leg} onPick={(a) => change.mutate({ action: "flight", leg, flight_id: a.catalog_id })} />
            ))}
            <AddAttraction id={id} pkg={data} onAdd={(attraction_id, day) => change.mutate({ action: "add_attraction", attraction_id, day })} />
            <Button size="lg" disabled={confirm.isPending || data.problems.length > 0} onClick={() => confirm.mutate()}>
              {confirm.isPending ? "Confirming…" : `Confirm ${inr(data.total_inr)}`}
            </Button>
            <FormError error={confirm.error} />
          </>
        ) : (
          <Link className="underline" href={`/holiday/reservation?ref=${data.reference}`}>
            Reservation {data.reference}
          </Link>
        )}
      </div>
    </div>
  );
}

function useAlternatives(id: string, kind: string, key?: string) {
  return useQuery({
    queryKey: ["holiday", "alternatives", id, kind, key],
    queryFn: () => apiFetch<Alternative[]>(`/holiday/packages/${id}/alternatives?kind=${kind}${key ? `&key=${encodeURIComponent(key)}` : ""}`),
  });
}

function Picker({ title, items, onPick }: { title: string; items: Alternative[]; onPick: (a: Alternative) => void }) {
  const [value, setValue] = useState("");
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <Select value={value} onValueChange={setValue}>
          <SelectTrigger aria-label={title}>
            <SelectValue placeholder="Choose…" />
          </SelectTrigger>
          <SelectContent>
            {items.map((a) => (
              <SelectItem key={`${a.catalog_id}-${a.room_id ?? ""}`} value={`${a.catalog_id}|${a.room_id ?? ""}`}>
                {a.name} · {a.detail} · {a.difference_inr >= 0 ? "+" : "−"}
                {inr(Math.abs(a.difference_inr))}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          disabled={!value}
          onClick={() => {
            const found = items.find((a) => `${a.catalog_id}|${a.room_id ?? ""}` === value);
            if (found) onPick(found);
          }}
        >
          Apply
        </Button>
      </CardContent>
    </Card>
  );
}

function ChangeHotel({ id, city, onPick }: { id: string; city: string; onPick: (a: Alternative) => void }) {
  const alts = useAlternatives(id, "hotel", city);
  return <Picker title={`Change hotel in ${city}`} items={alts.data ?? []} onPick={onPick} />;
}

function ChangeFlight({ id, leg, onPick }: { id: string; leg: "arrival" | "return"; onPick: (a: Alternative) => void }) {
  const alts = useAlternatives(id, "flight", leg);
  return <Picker title={leg === "arrival" ? "Change arrival flight" : "Change return flight"} items={alts.data ?? []} onPick={onPick} />;
}

function AddAttraction({ id, pkg, onAdd }: { id: string; pkg: Package; onAdd: (attraction: string, day: string) => void }) {
  const alts = useAlternatives(id, "attraction");
  const [attraction, setAttraction] = useState("");
  const [day, setDay] = useState(String(pkg.request.start_date));
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Add an attraction</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <Select value={attraction} onValueChange={setAttraction}>
          <SelectTrigger aria-label="Attraction">
            <SelectValue placeholder="Choose…" />
          </SelectTrigger>
          <SelectContent>
            {(alts.data ?? []).map((a) => (
              <SelectItem key={a.catalog_id} value={a.catalog_id}>
                {a.name} · {a.detail} · +{inr(a.price_inr)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input type="date" aria-label="Visit day" value={day} onChange={(e) => setDay(e.target.value)} />
        <Button variant="outline" disabled={!attraction} onClick={() => onAdd(attraction, day)}>
          Add
        </Button>
      </CardContent>
    </Card>
  );
}

// ── M7: open a reservation by its number ─────────────────────────────────────────────────────

export function ReservationView() {
  const params = useSearchParams();
  const router = useRouter();
  const ref = params.get("ref") ?? "";
  const [value, setValue] = useState(ref);
  const found = useQuery({
    queryKey: ["holiday", "reservation", ref],
    queryFn: () => apiFetch<Package>(`/holiday/reservations/${encodeURIComponent(ref)}`),
    enabled: ref.length > 0,
    retry: false,
  });
  return (
    <div className="grid gap-6">
      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          router.push(`/holiday/reservation?ref=${encodeURIComponent(value.trim())}`);
        }}
      >
        <Input aria-label="Reservation number" placeholder="10-digit reservation number" value={value} onChange={(e) => setValue(e.target.value)} />
        <Button type="submit">Open</Button>
      </form>
      {ref && found.isPending ? <Skeleton className="h-64 w-full" /> : null}
      {ref && found.error ? <p className="text-destructive">Reservation not found.</p> : null}
      {found.data ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <div className="grid content-start gap-3">
            <h1 className="flex flex-wrap items-baseline gap-x-4">
              Reservation
              <span className="font-sans text-xl font-semibold tracking-widest text-muted-foreground normal-case">{found.data.reference}</span>
            </h1>
            <p className="text-muted-foreground">
              {String(found.data.request.country)} · {found.data.cities.map((c) => `${c.city as string} ${c.nights as number}n`).join(" → ")} · Confirmed
            </p>
            <DayPlan pkg={found.data} />
          </div>
          <Totals pkg={found.data} />
        </div>
      ) : null}
    </div>
  );
}

// ── My Trips: confirmed holidays with their 10-digit reservation numbers ─────────────────────

export function HolidayReservations() {
  const mine = useQuery({ queryKey: ["holiday", "mine"], queryFn: () => apiFetch<Package[]>("/holiday/reservations") });
  if (!mine.data?.length) return null;
  return (
    <section className="grid gap-3">
      <h2 className="text-lg font-semibold">Holidays</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {mine.data.map((p) => (
          <Link key={p.id} href={`/holiday/reservation?ref=${p.reference}`} className="group">
            <Card className="h-full gap-2 p-5 transition-colors group-hover:border-primary/40">
              <div className="flex items-start justify-between gap-2">
                <p className="text-lg font-semibold">{String(p.request.country)} holiday</p>
                <Badge variant="secondary">Confirmed</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {p.cities.map((c) => `${c.city as string} ${c.nights as number}n`).join(" → ")} · from {dayName(String(p.request.start_date))}
              </p>
              <p className="text-sm">
                Reservation <span className="font-mono font-semibold">{p.reference}</span> · {inr(p.total_inr)}
              </p>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
