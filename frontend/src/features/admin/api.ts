"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/api/use-query";

import { apiFetch, type Schemas } from "@/lib/api/client";

export type ImportRun = Schemas["ImportRunOut"];
export type ImportRunDetail = Schemas["ImportRunDetailOut"];
export type RejectPage = Schemas["RejectPage"];

export function useImportRuns() {
  return useQuery({
    queryKey: ["admin", "imports"],
    queryFn: () => apiFetch<Schemas["ImportRunPage"]>("/admin/imports?limit=50"),
  });
}

export function useMappings() {
  return useQuery({
    queryKey: ["admin", "mappings"],
    queryFn: () => apiFetch<Schemas["MappingListOut"]>("/admin/imports/mappings"),
  });
}

export function useImportRun(id: string) {
  return useQuery({
    queryKey: ["admin", "imports", id],
    queryFn: () => apiFetch<ImportRunDetail>(`/admin/imports/${id}`),
  });
}

export function useRejects(id: string, query: string) {
  return useQuery({
    queryKey: ["admin", "imports", id, "rejects", query],
    queryFn: () => apiFetch<RejectPage>(`/admin/imports/${id}/rejects?${query}`),
  });
}

export function useStartImport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; mapping: string; dryRun: boolean }) => {
      const form = new FormData();
      form.append("file", input.file);
      form.append("mapping", input.mapping);
      form.append("dry_run", String(input.dryRun));
      return apiFetch<ImportRun>("/admin/imports", { method: "POST", body: form });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["admin", "imports"] });
      void client.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}
