import { ArrowRight, BedDouble, Plane, Route } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { siteConfig } from "@/config/site";

/**
 * Entry modes. `available` flips to true as each journey ships, so the home page never links
 * to a flow that does not exist yet.
 */
const modes = [
  {
    icon: Plane,
    title: "Book a flight",
    description: "Search by route and date, compare fares and stops, and book in a few steps.",
    available: false,
  },
  {
    icon: BedDouble,
    title: "Book a stay",
    description: "Find hotels by city, dates and guests, with the full price shown before you pay.",
    available: false,
  },
  {
    icon: Route,
    title: "Plan the whole trip",
    description: "Describe your trip and compare complete flight-and-hotel options side by side.",
    available: false,
  },
] as const;

export default function HomePage() {
  return (
    <>
      <section className="border-b bg-gradient-to-b from-primary/5 to-background">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-20 md:py-28">
          <Badge variant="secondary" className="w-fit">
            Flights · Stays · Connected trips
          </Badge>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance md:text-5xl">
            {siteConfig.tagline}
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground text-pretty">{siteConfig.description}</p>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/sign-up">
                Create a free account <ArrowRight />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/about">How TripMind works</Link>
            </Button>
          </div>
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
          {modes.map(({ icon: Icon, title, description, available }) => (
            <Card key={title} className="h-full">
              <CardHeader className="gap-3">
                <div className="flex items-center justify-between">
                  <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-5" aria-hidden />
                  </span>
                  {available ? null : <Badge variant="outline">Coming soon</Badge>}
                </div>
                <CardTitle>{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>
    </>
  );
}
