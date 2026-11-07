"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toQuery } from "@/features/search/api";
import { addDays } from "@/features/search/format";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";

type Parsed = Schemas["ParsedSearchOut"];

const MISSING: Record<string, string> = {
  origin: "where you're leaving from",
  destination: "a destination we have data for",
  depart_date: "a date",
  return_date: "a return date",
};

/** Where to send the traveller: the parsed criteria prefill the normal search forms. */
function destinationUrl(p: Parsed): string {
  if (p.intent === "stays") {
    return `/stays?${toQuery({
      city: p.destination?.city_id,
      cityName: p.destination?.label,
      checkIn: p.depart_date,
      checkOut: p.return_date ?? (p.depart_date ? addDays(p.depart_date, 2) : undefined),
      guests: p.adults,
      rooms: Math.max(1, Math.ceil(p.adults / 2)),
      stars: p.min_stars ? [String(p.min_stars), ...["4", "5"].filter((s) => Number(s) > p.min_stars!)] : undefined,
    })}`;
  }
  if (p.intent === "flights") {
    return `/flights?${toQuery({
      from: p.origin?.airport_code ?? p.origin?.city_id,
      fromLabel: p.origin?.label,
      to: p.destination?.airport_code ?? p.destination?.city_id,
      toLabel: p.destination?.label,
      depart: p.depart_date,
      return: p.return_date,
      adults: p.adults,
      cabin: p.cabin_class ?? "economy",
    })}`;
  }
  return `/plan?${toQuery({
    origin: p.origin?.airport_code ?? p.origin?.city_id,
    originLabel: p.origin?.label,
    dest: p.destination?.city_id,
    destLabel: p.destination?.label,
    depart: p.depart_date,
    return: p.return_date,
    adults: p.adults,
    priority: p.priority,
    budget: p.max_budget,
    stars: p.min_stars,
  })}`;
}

export function AiSearch() {
  const router = useRouter();
  const [text, setText] = useState("");
  const parse = useMutation({
    mutationFn: (value: string) => apiFetch<Parsed>("/ai/parse-search", { method: "POST", body: { text: value } }),
  });
  const result = parse.data;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (text.trim().length >= 3) parse.mutate(text.trim());
  }

  return (
    <div className="grid gap-2">
      <form onSubmit={submit} className="flex gap-2">
        <div className="relative flex-1">
          <Sparkles className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-primary" aria-hidden />
          <Input
            aria-label="Describe your trip"
            className="h-11 pl-9"
            placeholder="Describe your trip: “2 of us, Delhi to Goa next Friday for 4 nights under 60k”"
            value={text}
            maxLength={300}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <Button type="submit" size="lg" className="h-11" disabled={parse.isPending}>
          {parse.isPending ? "Reading…" : "Go"}
        </Button>
      </form>
      {parse.error ? <p className="text-sm text-destructive">{errorMessage(parse.error)}</p> : null}
      {result ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-3 text-sm">
          <Badge variant="outline">{result.source === "rules" ? "Understood by rules" : `Understood by AI (${result.source.slice(3)})`}</Badge>
          <span className="font-medium">{result.summary}</span>
          {result.missing.length ? (
            <span className="text-muted-foreground">
              · still need {result.missing.map((m) => MISSING[m] ?? m).join(", ")}
            </span>
          ) : null}
          {result.unknown_places.length ? (
            <span className="text-amber-700 dark:text-amber-300">· not in our data: {result.unknown_places.join(", ")}</span>
          ) : null}
          <Button size="sm" className="ml-auto" onClick={() => router.push(destinationUrl(result))}>
            {result.missing.length ? "Fill in the rest" : result.intent === "trip" ? "Plan this trip" : "Search"} <ArrowRight />
          </Button>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Don&apos;t include personal details. AI only fills in the form; you still choose and book.
        </p>
      )}
    </div>
  );
}
