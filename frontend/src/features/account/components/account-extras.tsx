"use client";

import { Award, Trash2, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { useAddTraveller, useDeleteTraveller, useLoyalty, useSavedTravellers } from "../api";

const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function LoyaltyCard() {
  const { data, isPending } = useLoyalty();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Award className="size-4 text-amber-500" /> TripMind Rewards
        </CardTitle>
        <CardDescription>
          Earn {data?.points_per_100 ?? 1} point for every 100 you pay. Refunds take back the points they earned.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {isPending || !data ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-4">
              <span className="text-3xl font-semibold tabular-nums">{data.balance.toLocaleString("en-IN")}</span>
              <span className="pb-1 text-sm">
                points · <span className="font-medium">{data.tier}</span> tier
                {data.next_tier ? (
                  <span className="text-muted-foreground">
                    {" "}
                    · {data.points_to_next_tier} to {data.next_tier}
                  </span>
                ) : null}
              </span>
            </div>
            {data.history.length ? (
              <ul className="grid gap-1 text-sm">
                {data.history.slice(0, 6).map((e, i) => (
                  <li key={i} className="flex justify-between gap-2">
                    <span className="text-muted-foreground">
                      {e.reason} · {when.format(new Date(e.created_at))}
                    </span>
                    <span className={`tabular-nums ${e.points < 0 ? "text-destructive" : "text-emerald-700 dark:text-emerald-400"}`}>
                      {e.points > 0 ? "+" : ""}
                      {e.points}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No points yet. Book a trip to start earning.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function SavedTravellersCard() {
  const { data, isPending } = useSavedTravellers();
  const add = useAddTraveller();
  const remove = useDeleteTraveller();
  const [form, setForm] = useState({ first_name: "", last_name: "", date_of_birth: "" });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.first_name.trim() || !form.last_name.trim()) return;
    add.mutate(
      { first_name: form.first_name, last_name: form.last_name, date_of_birth: form.date_of_birth || null },
      { onSuccess: () => setForm({ first_name: "", last_name: "", date_of_birth: "" }) },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Saved travellers</CardTitle>
        <CardDescription>People you often book for. Pick them at checkout instead of typing names again.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {isPending ? (
          <Skeleton className="h-10 w-full" />
        ) : data?.items.length ? (
          <ul className="grid gap-2">
            {data.items.map((t) => (
              <li key={t.id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <span>
                  {t.first_name} {t.last_name}
                  {t.date_of_birth ? <span className="text-muted-foreground"> · born {t.date_of_birth}</span> : null}
                </span>
                <Button size="icon" variant="ghost" aria-label={`Remove ${t.first_name}`} onClick={() => remove.mutate(t.id)}>
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No saved travellers yet.</p>
        )}
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_1fr_10rem_auto] md:items-end">
          <div className="grid gap-1.5">
            <Label htmlFor="st-first">First name</Label>
            <Input id="st-first" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="st-last">Last name</Label>
            <Input id="st-last" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="st-dob">Date of birth</Label>
            <Input id="st-dob" type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} />
          </div>
          <Button type="submit" disabled={add.isPending}>
            <UserPlus /> Save
          </Button>
        </form>
        {add.error ? <p className="text-sm text-destructive">{errorMessage(add.error)}</p> : null}
      </CardContent>
    </Card>
  );
}
