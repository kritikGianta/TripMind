"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { FormError } from "@/features/auth/components/form-error";
import { useSession } from "@/features/auth/hooks";
import { toQuery } from "@/features/search/api";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { useQuery } from "@/lib/api/use-query";

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

const PAGE = 25;

export function UsersView() {
  const { user: me } = useSession();
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const { data, error, isPending } = useQuery({
    queryKey: ["admin", "users", q, page],
    queryFn: () => apiFetch<Schemas["AdminUserPageOut"]>(`/admin/users?${toQuery({ q, limit: PAGE, offset: page * PAGE })}`),
  });
  const setActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      apiFetch<Schemas["AdminUserOut"]>(`/admin/users/${id}/status`, { method: "POST", body: { active } }),
    onSuccess: (user) => toast.success(`${user.email} ${user.is_active ? "enabled" : "disabled"}.`),
    onError: (issue) => toast.error(errorMessage(issue)),
    onSettled: () => void client.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Accounts</CardTitle>
        <CardDescription>Disabling an account ends its sessions at once. Every change is written to the audit log.</CardDescription>
        <form
          className="mt-2 flex max-w-md gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(0);
            setQ(text.trim());
          }}
        >
          <Input aria-label="Search accounts" placeholder="Name or email" value={text} onChange={(e) => setText(e.target.value)} />
          <Button type="submit" variant="outline">
            <Search /> Search
          </Button>
        </form>
      </CardHeader>
      <CardContent className="grid gap-2">
        {isPending ? <Skeleton className="h-40 w-full" /> : null}
        {error ? <FormError error={error} /> : null}
        {data?.items.map((user) => (
          <div key={user.id} className="grid gap-2 border-t py-2 first:border-0 sm:grid-cols-[1fr_auto] sm:items-center">
            <div className="min-w-0">
              <p className="truncate font-medium">
                {user.full_name} {user.role === "admin" ? <Badge variant="secondary">Admin</Badge> : null} {!user.is_active ? <Badge variant="destructive">Disabled</Badge> : null}
              </p>
              <p className="truncate text-sm text-muted-foreground">{user.email}</p>
              <p className="text-xs text-muted-foreground">
                {user.bookings} booking{user.bookings === 1 ? "" : "s"} · joined {day.format(new Date(user.created_at))}
                {user.last_login_at ? ` · last in ${day.format(new Date(user.last_login_at))}` : ""}
              </p>
            </div>
            {user.id !== me?.id ? (
              <Button variant="outline" size="sm" disabled={setActive.isPending} onClick={() => setActive.mutate({ id: user.id, active: !user.is_active })}>
                {user.is_active ? "Disable" : "Enable"}
              </Button>
            ) : (
              <span className="text-xs text-muted-foreground">This is you</span>
            )}
          </div>
        ))}
        {data && data.total > PAGE ? (
          <div className="flex items-center justify-between gap-2 border-t pt-3 text-sm">
            <span className="text-muted-foreground">
              {page * PAGE + 1} to {Math.min((page + 1) * PAGE, data.total)} of {data.total}
            </span>
            <span className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={(page + 1) * PAGE >= data.total} onClick={() => setPage(page + 1)}>
                Next
              </Button>
            </span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
