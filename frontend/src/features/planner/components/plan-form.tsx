"use client";

import { AlertCircle, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDataset } from "@/features/search/api";
import { LocationPicker, type PickedLocation } from "@/features/search/components/location-picker";
import { addDays, todayIso } from "@/features/search/format";
import { errorMessage } from "@/lib/api/errors";

import { useCreatePlan, type PlanRequest } from "../api";

const PRIORITIES: Array<{ value: PlanRequest["priority"]; label: string; hint: string }> = [
  { value: "balanced", label: "Balanced", hint: "Price, time, stay and convenience together" },
  { value: "cheapest", label: "Lowest price", hint: "Price counts most" },
  { value: "fastest", label: "Least travel time", hint: "Shortest flying time counts most" },
  { value: "comfort", label: "Best stay", hint: "Hotel quality and convenience count most" },
];

export function PlanForm() {
  const router = useRouter();
  const create = useCreatePlan();
  const { data: dataset } = useDataset();
  const tomorrow = addDays(todayIso(), 1);
  const first = dataset?.travel_window?.first_departure;
  const start = first && first > tomorrow ? first : tomorrow;

  const [from, setFrom] = useState<PickedLocation | null>(null);
  const [to, setTo] = useState<PickedLocation | null>(null);
  const [depart, setDepart] = useState("");
  const [ret, setRet] = useState("");
  const [adults, setAdults] = useState(2);
  const [priority, setPriority] = useState<PlanRequest["priority"]>("balanced");
  const [minStars, setMinStars] = useState("any");
  const [budget, setBudget] = useState("");
  const [error, setError] = useState<string | null>(null);

  const departValue = depart || start;
  const returnValue = ret || addDays(departValue, 3);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!from || !to) return setError("Choose where you're leaving from and where you're going.");
    if (returnValue <= departValue) return setError("Come back at least one day after you leave.");
    setError(null);
    create.mutate(
      {
        origin: from.value,
        destination_city_id: to.value,
        depart_date: departValue,
        return_date: returnValue,
        adults,
        priority,
        min_stars: minStars === "any" ? null : Number(minStars),
        max_budget: budget ? Number(budget) : null,
      },
      { onSuccess: (plan) => router.push(`/plans/${plan.id}`) },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" /> Plan the whole trip
        </CardTitle>
        <CardDescription>
          TripMind combines flights both ways with a stay for the nights in between, checks that they fit together, and
          ranks complete trips. Every rank comes with the reasons behind it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4" noValidate>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="plan-from">Leaving from</Label>
              <LocationPicker id="plan-from" kind="airport" value={from} onChange={setFrom} placeholder="City or airport" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="plan-to">Going to</Label>
              <LocationPicker id="plan-to" kind="city" value={to} onChange={setTo} placeholder="Destination city" />
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="grid gap-1.5">
              <Label htmlFor="plan-depart">Leave on</Label>
              <Input id="plan-depart" type="date" className="h-11" value={departValue} min={todayIso()}
                max={dataset?.travel_window?.last_departure} onChange={(e) => setDepart(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="plan-return">Come back on</Label>
              <Input id="plan-return" type="date" className="h-11" value={returnValue} min={addDays(departValue, 1)}
                max={dataset?.travel_window?.last_departure} onChange={(e) => setRet(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="plan-adults">Travellers</Label>
              <Select value={String(adults)} onValueChange={(v) => setAdults(Number(v))}>
                <SelectTrigger id="plan-adults" className="!h-11 w-full">
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
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="plan-stars">Hotel</Label>
              <Select value={minStars} onValueChange={setMinStars}>
                <SelectTrigger id="plan-stars" className="!h-11 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Any stars</SelectItem>
                  {[3, 4, 5].map((s) => (
                    <SelectItem key={s} value={String(s)}>
                      {s} stars or more
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <fieldset className="grid gap-2">
            <legend className="mb-1 text-sm font-medium">What matters most?</legend>
            <div className="grid gap-2 md:grid-cols-4">
              {PRIORITIES.map((p) => (
                <label
                  key={p.value}
                  className={`cursor-pointer rounded-lg border p-3 text-sm transition-colors ${priority === p.value ? "border-primary bg-primary/5" : "hover:bg-muted/50"}`}
                >
                  <input type="radio" name="priority" value={p.value} checked={priority === p.value}
                    onChange={() => setPriority(p.value)} className="sr-only" />
                  <span className="font-medium">{p.label}</span>
                  <span className="block text-xs text-muted-foreground">{p.hint}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="grid gap-3 md:grid-cols-[14rem_1fr] md:items-end">
            <div className="grid gap-1.5">
              <Label htmlFor="plan-budget">Total budget in ₹ (optional)</Label>
              <Input id="plan-budget" inputMode="numeric" placeholder="e.g. 60000" value={budget}
                onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))} />
            </div>
            <Button type="submit" size="lg" className="h-11 md:w-fit" disabled={create.isPending}>
              {create.isPending ? "Planning…" : "Plan my trip"}
            </Button>
          </div>
          {error || create.error ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{error ?? errorMessage(create.error)}</AlertDescription>
            </Alert>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
