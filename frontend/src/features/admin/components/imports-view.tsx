"use client";

import { AlertCircle, FileArchive, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage } from "@/lib/api/errors";

import { useImportRuns, useMappings, useStartImport, type ImportRun } from "../api";

const STATUS_STYLE: Record<string, string> = {
  published: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  validated: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  blocked: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  failed: "bg-destructive/15 text-destructive",
  running: "bg-muted text-muted-foreground",
};

export function StatusPill({ status }: { status: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLE[status] ?? ""}`}>{status}</span>;
}

const dateTime = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

function totals(run: ImportRun) {
  const counts = Object.entries(run.entity_counts ?? {}).filter(([entity]) => entity !== "cities");
  return {
    read: counts.reduce((n, [, c]) => n + (c.read ?? 0), 0),
    rejected: counts.reduce((n, [, c]) => n + (c.rejected ?? 0), 0),
  };
}

function UploadCard() {
  const router = useRouter();
  const mappings = useMappings();
  const start = useStartImport();
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<string>("");
  const [dryRun, setDryRun] = useState(true);
  const chosenMapping = mapping || mappings.data?.mappings[0] || "";

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || !chosenMapping) return;
    start.mutate(
      { file, mapping: chosenMapping, dryRun },
      {
        onSuccess: (run) => {
          toast.success(`Import ${run.status}`);
          router.push(`/admin/imports/${run.id}`);
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Upload className="size-4" /> Import a dataset
        </CardTitle>
        <CardDescription>
          A ZIP of CSV, JSON or Excel files plus a mapping from <code>config/mappings</code>. Start with a dry run: it
          validates everything and publishes nothing.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_14rem_auto_auto] md:items-end">
          <div className="grid gap-1.5">
            <Label htmlFor="dataset-file">Dataset ZIP</Label>
            <Input id="dataset-file" type="file" accept=".zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="dataset-mapping">Mapping</Label>
            <Select value={chosenMapping} onValueChange={setMapping}>
              <SelectTrigger id="dataset-mapping" className="w-full">
                <SelectValue placeholder="Choose a mapping" />
              </SelectTrigger>
              <SelectContent>
                {(mappings.data?.mappings ?? []).map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex h-9 items-center gap-2">
            <Checkbox id="dry-run" checked={dryRun} onCheckedChange={(v) => setDryRun(v === true)} />
            <Label htmlFor="dry-run" className="font-normal">
              Dry run
            </Label>
          </div>
          <Button type="submit" disabled={!file || !chosenMapping || start.isPending}>
            {start.isPending ? "Importing…" : dryRun ? "Validate" : "Import and publish"}
          </Button>
        </form>
        {start.error ? (
          <Alert variant="destructive" className="mt-4">
            <AlertCircle />
            <AlertDescription>{errorMessage(start.error)}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function ImportsView() {
  const runs = useImportRuns();
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Data imports</h1>
        <p className="text-sm text-muted-foreground">
          Every catalog row enters through this pipeline: profile, map, validate, quarantine, publish, report.
        </p>
      </div>
      <UploadCard />
      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {runs.isPending ? (
            <Skeleton className="h-32 w-full" />
          ) : runs.error ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{errorMessage(runs.error)}</AlertDescription>
            </Alert>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 pr-4 font-medium">Started</th>
                  <th className="py-2 pr-4 font-medium">Dataset</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 text-right font-medium">Rows read</th>
                  <th className="py-2 pr-4 text-right font-medium">Rejected</th>
                  <th className="py-2 pr-4 text-right font-medium">Time</th>
                  <th className="py-2 font-medium">Via</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((run) => {
                  const t = totals(run);
                  return (
                    <tr key={run.id} className="border-b last:border-0 hover:bg-muted/40">
                      <td className="py-2 pr-4">
                        <Link href={`/admin/imports/${run.id}`} className="font-medium hover:underline">
                          {dateTime.format(new Date(run.started_at))}
                        </Link>
                      </td>
                      <td className="py-2 pr-4">
                        <span className="flex items-center gap-1.5">
                          <FileArchive className="size-3.5 text-muted-foreground" /> {run.dataset}
                          {run.dry_run ? <Badge variant="outline">dry run</Badge> : null}
                        </span>
                      </td>
                      <td className="py-2 pr-4">
                        <StatusPill status={run.status} />
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums">{t.read.toLocaleString("en-IN")}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{t.rejected.toLocaleString("en-IN")}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">
                        {run.duration_ms !== null && run.duration_ms !== undefined ? `${(run.duration_ms / 1000).toFixed(1)} s` : "—"}
                      </td>
                      <td className="py-2 uppercase text-muted-foreground">{run.triggered_via}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
