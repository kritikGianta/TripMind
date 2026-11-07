import { ArrowRight, BedDouble, Plane, Route } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { siteConfig } from "@/config/site";
import { AiSearch } from "@/features/ai/ai-search";
import { SearchPanel } from "@/features/search/components/search-panel";

/**
 * Entry modes. `href` is set as each journey ships, so the home page never links to a flow that
 * does not exist yet.
 */
const modes = [
  {
    icon: Plane,
    title: "Book a flight",
    description: "Search by route and date, compare fares, stops and journey times, one-way or return.",
    href: "/flights",
  },
  {
    icon: BedDouble,
    title: "Book a stay",
    description: "Find hotels by city, dates and guests, with the price for the whole stay shown upfront.",
    href: "/stays",
  },
  {
    icon: Route,
    title: "Plan the whole trip",
    description: "Give dates and a destination; compare complete flight-and-stay trips, ranked with reasons.",
    href: "/plan",
  },
] as const;

export default function HomePage() {
  return (
    <>
      <section className="border-b bg-gradient-to-b from-primary/5 to-background">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-14 md:py-20">
          <Badge variant="secondary" className="w-fit">
            Flights · Stays · Connected trips
          </Badge>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance md:text-5xl">
            {siteConfig.tagline}
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground text-pretty">{siteConfig.description}</p>
          <AiSearch />
          <Suspense fallback={<Skeleton className="h-40 w-full" />}>
            <SearchPanel />
          </Suspense>
        </div>
      </section>

      <section aria-labelledby="modes-heading" className="mx-auto w-full max-w-6xl px-4 py-16">
        <h2 id="modes-heading" className="mb-2 text-2xl font-semibold tracking-tight">
          Three ways to book
        </h2>
        <p className="mb-8 text-muted-foreground">
          Book one product on its own, or let TripMind plan the flight and the stay together.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {modes.map(({ icon: Icon, title, description, href }) => {
            const card = (
              <Card className="h-full transition-colors group-hover:border-primary/40">
                <CardHeader className="gap-3">
                  <div className="flex items-center justify-between">
                    <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="size-5" aria-hidden />
                    </span>
                    {href ? (
                      <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
                    ) : (
                      <Badge variant="outline">Coming soon</Badge>
                    )}
                  </div>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{description}</CardDescription>
                </CardHeader>
              </Card>
            );
            return href ? (
              <Link key={title} href={href} className="group rounded-xl focus-visible:outline-2 focus-visible:outline-primary">
                {card}
              </Link>
            ) : (
              <div key={title}>{card}</div>
            );
          })}
        </div>
      </section>
    </>
  );
}
