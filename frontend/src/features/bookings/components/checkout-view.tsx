"use client";

import { AlertCircle, BedDouble, Lock, Plane } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useSavedTravellers } from "@/features/account/api";
import { useSession } from "@/features/auth/hooks";
import { PriceBreakdown } from "@/features/search/components/price-breakdown";
import { formatMoney } from "@/features/search/format";
import { ApiError, errorMessage } from "@/lib/api/errors";

import { useCreateBooking, useQuote, type ItemIn } from "../api";

type TravellerForm = { first_name: string; last_name: string; date_of_birth: string };

const dateTime = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function useCheckoutItems(): { items: ItemIn[] | null; adults: number; tripId: string | null } {
  const params = useSearchParams();
  return useMemo(() => {
    const adults = Number(params.get("adults") ?? 1);
    const items: ItemIn[] = params.getAll("flight").map((offer_id) => ({ kind: "flight", offer_id, adults }));
    const room = params.get("room");
    if (room && params.get("checkIn") && params.get("checkOut")) {
      items.push({
        kind: "hotel",
        room_type_id: room,
        check_in: params.get("checkIn")!,
        check_out: params.get("checkOut")!,
        rooms: Number(params.get("rooms") ?? 1),
        guests: Number(params.get("guests") ?? 2),
      });
    }
    return { items: items.length ? items : null, adults, tripId: params.get("trip") };
  }, [params]);
}

export function CheckoutView() {
  const router = useRouter();
  const { user } = useSession();
  const { items, adults, tripId } = useCheckoutItems();
  const [promoInput, setPromoInput] = useState("");
  const [promo, setPromo] = useState<string | null>(null);
  const quote = useQuote(items, promo);
  const saved = useSavedTravellers(Boolean(user));
  const hasFlight = items?.some((i) => i.kind === "flight") ?? false;
  const travellerCount = hasFlight ? adults : 1;

  // One key per checkout page: double-clicks and retries reuse it and get the same booking.
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const create = useCreateBooking(idempotencyKey);
  const [travellers, setTravellers] = useState<TravellerForm[]>(() =>
    Array.from({ length: travellerCount }, () => ({ first_name: "", last_name: "", date_of_birth: "" })),
  );
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const contactEmail = email || user?.email || "";

  if (!items) {
    return (
      <Alert>
        <AlertCircle />
        <AlertDescription>Nothing to check out. Choose a flight or a room first.</AlertDescription>
      </Alert>
    );
  }

  function update(index: number, field: keyof TravellerForm, value: string) {
    setTravellers((current) => current.map((t, i) => (i === index ? { ...t, [field]: value } : t)));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (travellers.some((t) => !t.first_name.trim() || !t.last_name.trim())) {
      return setFormError("Enter a first and last name for every traveller, as on their ID.");
    }
    if (!/^\S+@\S+\.\S+$/.test(contactEmail)) return setFormError("Enter a valid email for your confirmation.");
    setFormError(null);
    create.mutate(
      {
        items: items!,
        travellers: travellers.map((t) => ({
          first_name: t.first_name.trim(),
          last_name: t.last_name.trim(),
          date_of_birth: t.date_of_birth || null,
        })),
        contact: { email: contactEmail, phone: phone || null },
        trip_id: tripId,
        promo_code: promo,
        expected_total_minor: quote.data?.total.amount_minor ?? null,
      },
      { onSuccess: (booking) => router.push(`/bookings/${booking.id}`) },
    );
  }

  const priceChanged = create.error instanceof ApiError && create.error.code === "PRICE_CHANGED";

  return (
    <form onSubmit={submit} className="grid gap-6 md:grid-cols-[1fr_22rem]" noValidate>
      <div className="grid content-start gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Checkout</h1>
          <p className="text-sm text-muted-foreground">
            {tripId ? "Adding to an existing trip. " : ""}Review, add traveller details, then confirm. No payment is needed.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Your selection</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {quote.isPending ? (
              <Skeleton className="h-24 w-full" />
            ) : quote.error ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertDescription>{errorMessage(quote.error)}</AlertDescription>
              </Alert>
            ) : (
              quote.data.items.map((item, i) => (
                <div key={i} className="grid gap-2 border-b pb-4 last:border-0 last:pb-0 md:grid-cols-[1fr_auto]">
                  <div className="grid gap-1">
                    <div className="flex items-center gap-2 font-medium">
                      {item.kind === "flight" ? <Plane className="size-4" /> : <BedDouble className="size-4" />}
                      {item.title}
                    </div>
                    <p className="text-sm text-muted-foreground">{item.subtitle}</p>
                    <p className="text-xs text-muted-foreground">
                      {dateTime.format(new Date(item.starts_at))} → {dateTime.format(new Date(item.ends_at))} (your time zone)
                    </p>
                    <p className="text-xs">
                      <Badge variant="outline" className="mr-1">
                        Cancellation
                      </Badge>
                      {item.policy}
                    </p>
                  </div>
                  <PriceBreakdown ledger={item.price} />
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{hasFlight ? "Travellers" : "Lead guest"}</CardTitle>
            <CardDescription>Names exactly as on the passport or ID used to travel.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {saved.data?.items.length ? (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">Saved:</span>
                {saved.data.items.map((s) => (
                  <Button
                    key={s.id}
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const slot = travellers.findIndex((t) => !t.first_name && !t.last_name);
                      const index = slot === -1 ? 0 : slot;
                      setTravellers((current) =>
                        current.map((t, i) =>
                          i === index ? { first_name: s.first_name, last_name: s.last_name, date_of_birth: s.date_of_birth ?? "" } : t,
                        ),
                      );
                    }}
                  >
                    {s.first_name} {s.last_name}
                  </Button>
                ))}
              </div>
            ) : null}
            {travellers.map((t, i) => (
              <fieldset key={i} className="grid gap-3 md:grid-cols-3">
                <legend className="mb-1 text-sm font-medium">{hasFlight ? `Adult ${i + 1}` : "Guest"}</legend>
                <div className="grid gap-1.5">
                  <Label htmlFor={`first-${i}`}>First name</Label>
                  <Input id={`first-${i}`} value={t.first_name} onChange={(e) => update(i, "first_name", e.target.value)} autoComplete="given-name" />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor={`last-${i}`}>Last name</Label>
                  <Input id={`last-${i}`} value={t.last_name} onChange={(e) => update(i, "last_name", e.target.value)} autoComplete="family-name" />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor={`dob-${i}`}>Date of birth (optional)</Label>
                  <Input id={`dob-${i}`} type="date" value={t.date_of_birth} onChange={(e) => update(i, "date_of_birth", e.target.value)} />
                </div>
              </fieldset>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Contact</CardTitle>
            <CardDescription>Where we send the confirmation.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={contactEmail} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="phone">Phone (optional)</Label>
              <Input id="phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" />
            </div>
          </CardContent>
        </Card>
      </div>

      <aside className="grid content-start gap-4 md:sticky md:top-20">
        <Card>
          <CardHeader>
            <CardTitle>Price summary</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            {quote.data ? (
              <>
                {quote.data.items.map((item, i) => (
                  <div key={i} className="flex justify-between gap-2">
                    <span className="text-muted-foreground">{item.title}</span>
                    <span className="tabular-nums">{formatMoney(item.price.display_total)}</span>
                  </div>
                ))}
                {quote.data.discount ? (
                  <div className="flex justify-between gap-2 text-emerald-700 dark:text-emerald-400">
                    <span>Promo {quote.data.promo_code}</span>
                    <span className="tabular-nums">−{formatMoney(quote.data.discount)}</span>
                  </div>
                ) : null}
                <div className="flex justify-between border-t pt-3 text-base font-semibold">
                  <span>Total</span>
                  <span className="tabular-nums">{formatMoney(quote.data.total)}</span>
                </div>
                {!quote.data.complete ? (
                  <p className="text-xs text-muted-foreground">Taxes and fees are not included in the supplied data.</p>
                ) : null}
                {quote.data.fx_note ? <p className="text-xs text-muted-foreground">{quote.data.fx_note}</p> : null}
              </>
            ) : (
              <Skeleton className="h-16 w-full" />
            )}
            <div className="flex gap-2">
              <Input
                aria-label="Promo code"
                placeholder="Promo code"
                value={promoInput}
                onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
              />
              <Button type="button" variant="outline" onClick={() => setPromo(promoInput.trim() || null)}>
                Apply
              </Button>
            </div>
            {promo && quote.error ? (
              <p className="text-xs text-destructive">
                {errorMessage(quote.error)}{" "}
                <button type="button" className="underline" onClick={() => { setPromo(null); setPromoInput(""); }}>
                  Remove code
                </button>
              </p>
            ) : quote.data?.promo_description ? (
              <p className="text-xs text-muted-foreground">{quote.data.promo_description}</p>
            ) : (
              <p className="text-xs text-muted-foreground">Try WELCOME10, STAYLONGER or TRIPTOGETHER.</p>
            )}
            {formError || create.error ? (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertDescription>
                  {formError ??
                    (priceChanged ? "The price changed while you were checking out. The new price is shown; review it and try again." : errorMessage(create.error))}
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="submit"
              size="lg"
              disabled={!quote.data || create.isPending}
              onClick={() => priceChanged && void quote.refetch()}
            >
              <Lock /> {create.isPending ? "Confirming…" : "Confirm booking"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Confirming books the seats and rooms straight away and gives you a 10-digit reference.
            </p>
          </CardContent>
        </Card>
      </aside>
    </form>
  );
}
