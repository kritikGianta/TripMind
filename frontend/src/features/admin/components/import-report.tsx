"use client";

import { AlertCircle, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { useImportRun, useRejects } from "../api";
import { StatusPill } from "./imports-view";

const COLUMNS = ["read", "accepted", "rejected", "inserted", "updated", "unchanged", "retired"] as const;
const PAGE = 25;

const REASONS: Record<string, string> = {
  MISSING_REQUIRED: "A required value is empty",
  INVALID_VALUE: "Value can't be read as the expected type",
  OUT_OF_RANGE: "Value outside the allowed range",
  DUPLICATE_KEY: "Same identity as an earlier row",
  UNKNOWN_REFERENCE: "Refers to an airport or hotel that doesn't exist",
  INCONSISTENT: "Fields contradict each other",
};

function Rejects({ id, summary }: { id: string; summary: Record<string, Record<string, number>> }) {
  const [entity, setEntity] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const query = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (entity) query.set("entity", entity);
  if (code) query.set("code", code);
  const { data, isPending } = useRejects(id, query.toString());

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quarantined rows</CardTitle>
        <CardDescription>Kept with the reason and the original values, never silently dropped. Click a reason to filter.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={!entity ? "secondary" : "outline"} onClick={() => { setEntity(null); setCode(null); setOffset(0); }}>
            All
          </Button>
          {Object.entries(summary).flatMap(([ent, codes]) =>
            Object.entries(codes).map(([c, n]) => (
              <Button
                key={`${ent}-${c}`}
                size="sm"
                variant={entity === ent && code === c ? "secondary" : "outline"}
                onClick={() => { setEntity(ent); setCode(c); setOffset(0); }}
                title={REASONS[c]}
              >
                {ent} · {c} <Badge variant="outline">{n}</Badge>
              </Button>
            )),
          )}
        </div>
        {isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : data && data.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 pr-3 font-medium">File · row</th>
                  <th className="py-2 pr-3 font-medium">Reason</th>
                  <th className="py-2 pr-3 font-medium">Field</th>
                  <th className="py-2 font-medium">Original values</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={`${r.source_file}-${r.row_number}-${r.code}`} className="border-b align-top last:border-0">
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {r.source_file} · {r.row_number}
                    </td>
                    <td className="py-2 pr-3">
                      <Badge variant="outline">{r.code}</Badge>
                      <div className="mt-1 text-xs text-muted-foreground">{r.message}</div>
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs">{r.field ?? "—"}</td>
                    <td className="py-2 font-mono text-xs break-all text-muted-foreground">
                      {r.raw
                        ? Object.entries(r.raw)
                            .slice(0, 8)
                            .map(([k, v]) => `${k}=${v === null ? "∅" : String(v)}`)
                            .join("  ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total}
              </span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                  Previous
                </Button>
                <Button size="sm" variant="outline" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>
                  Next
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No rows were rejected.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function ImportReport() {
  const { id } = useParams<{ id: string }>();
  const { data: run, error, isPending } = useImportRun(id);

  if (isPending) return <Skeleton className="h-64 w-full" />;
  if (error || !run) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }

  const adjustments = Object.entries(run.adjustments ?? {});
  return (
    <div className="grid gap-6">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link href="/admin/imports">
          <ArrowLeft /> All imports
        </Link>
      </Button>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Import report</h1>
        <StatusPill status={run.status} />
        {run.dry_run ? <Badge variant="outline">dry run</Badge> : null}
      </div>
      <p className="text-sm text-muted-foreground">
        {run.dataset} · {run.source_name} · mapping {run.mapping_name} · {run.origin} data ·{" "}
        {run.duration_ms !== null && run.duration_ms !== undefined ? `${(run.duration_ms / 1000).toFixed(1)} s` : ""}
        {run.travel_window ? ` · flights ${run.travel_window.first_departure} to ${run.travel_window.last_departure}` : ""}
      </p>
      {run.error ? (
        <Alert variant={run.status === "failed" ? "destructive" : "default"}>
          <AlertCircle />
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Rows by entity</CardTitle>
          <CardDescription>
            Inserted, updated, unchanged and retired compare this file with what was already live. Cities are derived from
            airports and hotels.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="py-2 pr-4 text-left font-medium">Entity</th>
                {COLUMNS.map((c) => (
                  <th key={c} className="py-2 pr-4 text-right font-medium capitalize">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(run.entity_counts ?? {}).map(([entity, counts]) => (
                <tr key={entity} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">{entity.replace("_", " ")}</td>
                  {COLUMNS.map((c) => (
                    <td key={c} className={`py-2 pr-4 text-right tabular-nums ${c === "rejected" && counts[c] ? "text-destructive" : ""}`}>
                      {(counts[c] ?? 0).toLocaleString("en-IN")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {adjustments.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Normalisations applied</CardTitle>
            <CardDescription>Fixes made instead of rejecting rows. Each is counted so nothing is hidden.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            {adjustments.map(([code, n]) => (
              <div key={code} className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-2 last:border-0">
                <span className="font-mono text-xs">{code}</span>
                <span className="text-xs text-muted-foreground">{(run.adjustment_examples?.[code] ?? []).slice(0, 3).join(" · ")}</span>
                <span className="tabular-nums">{n}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Rejects id={run.id} summary={run.reject_summary ?? {}} />
    </div>
  );
}
