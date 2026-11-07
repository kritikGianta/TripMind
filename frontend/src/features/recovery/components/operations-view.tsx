"use client";

import { AlertCircle, CloudLightning } from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { useBookedFlights, useDisrupt, useDisruptions } from "../api";

const when = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Operator console: simulate what a real airline feed would send, and watch recovery start. */
export function OperationsView() {
  const flights = useBookedFlights();
  const history = useDisruptions();
  const disrupt = useDisrupt();

  function act(flightId: string, kind: "flight_cancelled" | "flight_delayed", delay?: number) {
    disrupt.mutate(
      {
        kind,
        flight_id: flightId,
        delay_minutes: delay ?? null,
        reason: kind === "flight_cancelled" ? "Cancelled by the airline (operational reasons)" : "Late inbound aircraft",
      },
      { onSuccess: (d) => toast.success(`Recorded. ${d.affected_items} booking item(s) affected; travellers notified.`) },
    );
  }

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <CloudLightning className="size-5" /> Disruptions
        </h1>
        <p className="text-sm text-muted-foreground">
          Stands in for an airline or hotel operations feed. Recording a disruption finds every affected booking, releases
          unpaid holds, and gives paid travellers recovery options to choose from.
        </p>
      </div>
      {disrupt.error ? (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{errorMessage(disrupt.error)}</AlertDescription>
        </Alert>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>Upcoming flights with bookings</CardTitle>
          <CardDescription>Book something as the demo traveller first, then come back here.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {flights.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : flights.data?.items.length ? (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 pr-3 font-medium">Flight</th>
                  <th className="py-2 pr-3 font-medium">Route</th>
                  <th className="py-2 pr-3 font-medium">Departs (local)</th>
                  <th className="py-2 pr-3 text-right font-medium">Seats sold</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {flights.data.items.map((f) => (
                  <tr key={f.flight_id} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-medium">{f.flight_number}</td>
                    <td className="py-2 pr-3">{f.route}</td>
                    <td className="py-2 pr-3">{when.format(new Date(f.departure_local))}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{f.booked_seats}</td>
                    <td className="py-2">
                      {f.disruption === "flight_cancelled" ? (
                        <Badge variant="outline">Cancelled</Badge>
                      ) : (
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="outline" disabled={disrupt.isPending} onClick={() => act(f.flight_id, "flight_delayed", 45)}>
                            Delay 45m
                          </Button>
                          <Button size="sm" variant="outline" disabled={disrupt.isPending} onClick={() => act(f.flight_id, "flight_delayed", 240)}>
                            Delay 4h
                          </Button>
                          <Button size="sm" variant="destructive" disabled={disrupt.isPending} onClick={() => act(f.flight_id, "flight_cancelled")}>
                            Cancel
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">No upcoming flights have seats sold yet.</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          {(history.data?.items ?? []).length === 0 ? (
            <p className="text-muted-foreground">No disruptions recorded.</p>
          ) : (
            history.data!.items.map((d) => (
              <div key={d.id} className="flex flex-wrap justify-between gap-2 border-b pb-2 last:border-0">
                <span>
                  <Badge variant="outline" className="mr-2">
                    {d.kind.replace("_", " ")}
                    {d.delay_minutes ? ` ${d.delay_minutes}m` : ""}
                  </Badge>
                  {d.target}
                </span>
                <span className="text-muted-foreground">
                  {d.affected_items} affected · {when.format(new Date(d.created_at))}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
