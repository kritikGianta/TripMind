"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/features/search/format";
import { apiFetch, type Schemas } from "@/lib/api/client";

type Analytics = Schemas["AnalyticsOut"];
type AuditPage = Schemas["AuditPageOut"];

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="gap-1 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </Card>
  );
}

function Bars({ title, rows }: { title: string; rows: Array<{ label: string; value: number }> }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        {rows.length ? (
          rows.map((r) => (
            <div key={r.label} className="grid grid-cols-[8rem_1fr_3rem] items-center gap-2 text-sm">
              <span className="truncate capitalize text-muted-foreground">{r.label.replace("_", " ")}</span>
              <span className="h-2 rounded-full bg-muted">
                <span className="block h-2 rounded-full bg-primary" style={{ width: `${(r.value / max) * 100}%` }} />
              </span>
              <span className="text-right tabular-nums">{r.value}</span>
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">No data yet.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function AnalyticsView() {
  const { data, isPending } = useQuery({
    queryKey: ["admin", "analytics"],
    queryFn: () => apiFetch<Analytics>("/admin/analytics"),
    refetchInterval: 30_000,
  });
  if (isPending || !data) return <Skeleton className="h-96 w-full" />;
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted-foreground">Straight from the database. {data.note}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Net booking value" value={formatMoney(data.net_value)} hint={`${formatMoney(data.refunded_value)} refunded`} />
        <Stat label="Average booking" value={formatMoney(data.average_booking_value)} />
        <Stat label="Holds that were paid" value={data.hold_conversion_percent === null ? "—" : `${data.hold_conversion_percent}%`} />
        <Stat label="Connected trips" value={String(data.connected_trips)} hint="Flight and stay in one trip" />
        <Stat label="Travellers" value={String(data.travellers)} />
        <Stat label="Trip plans generated" value={String(data.plans_generated)} />
        <Stat label="Bookings with a promo" value={String(data.promo_bookings)} />
        <Stat label="Booked items" value={String(data.items_by_kind.reduce((n, r) => n + r.value, 0))}
          hint={data.items_by_kind.map((r) => `${r.value} ${r.label}`).join(" · ")} />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Bars title="Bookings by status" rows={data.bookings_by_status} />
        <Bars title="Top destinations" rows={data.top_destinations} />
        <Bars title="Disruption cases" rows={data.recovery_by_status} />
      </div>
      <Bars title="Confirmed bookings, last 30 days" rows={data.last_30_days.map((d) => ({ label: d.day, value: d.bookings }))} />
    </div>
  );
}

const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function AuditView() {
  const [action, setAction] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const query = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (action) query.set("action", action);
  const { data, isPending } = useQuery({
    queryKey: ["admin", "audit", action, offset],
    queryFn: () => apiFetch<AuditPage>(`/admin/audit?${query}`),
  });
  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every sign-in, booking, payment, cancellation, import, disruption and recovery, with request ID and client
          address. Rows are never edited or deleted by the application.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={action ? "outline" : "secondary"} onClick={() => { setAction(null); setOffset(0); }}>
          All
        </Button>
        {(data?.actions ?? []).map((a) => (
          <Button key={a} size="sm" variant={action === a ? "secondary" : "outline"} onClick={() => { setAction(a); setOffset(0); }}>
            {a}
          </Button>
        ))}
      </div>
      <Card>
        <CardContent className="overflow-x-auto pt-6">
          {isPending || !data ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 pr-3 font-medium">When</th>
                  <th className="py-2 pr-3 font-medium">Action</th>
                  <th className="py-2 pr-3 font-medium">Outcome</th>
                  <th className="py-2 pr-3 font-medium">Who</th>
                  <th className="py-2 pr-3 font-medium">Request</th>
                  <th className="py-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row, i) => (
                  <tr key={i} className="border-b align-top last:border-0">
                    <td className="py-2 pr-3 whitespace-nowrap">{when.format(new Date(row.occurred_at))}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{row.action}</td>
                    <td className="py-2 pr-3">
                      <Badge variant={row.outcome === "failure" || row.outcome === "failed" ? "destructive" : "outline"}>{row.outcome}</Badge>
                    </td>
                    <td className="py-2 pr-3">{row.actor_email ?? "system"}</td>
                    <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">{row.request_id?.slice(0, 8) ?? "—"}</td>
                    <td className="py-2 font-mono text-xs break-all text-muted-foreground">
                      {row.details ? JSON.stringify(row.details) : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
      {data ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{data.total} events</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>
              Newer
            </Button>
            <Button size="sm" variant="outline" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>
              Older
            </Button>
          </div>
        </div>
      ) : null}
      <CardDescription>Request IDs match the X-Request-ID header and the API logs, so a support case can be traced end to end.</CardDescription>
    </div>
  );
}
