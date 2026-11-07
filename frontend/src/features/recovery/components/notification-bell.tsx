"use client";

import { Bell } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useSession } from "@/features/auth/hooks";
import { cn } from "@/lib/utils";

import { useMarkRead, useNotifications } from "../api";

const DOT: Record<string, string> = {
  critical: "bg-destructive",
  warning: "bg-amber-500",
  success: "bg-emerald-500",
  info: "bg-sky-500",
};

const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function NotificationBell() {
  const { user } = useSession();
  const { data } = useNotifications(Boolean(user));
  const markRead = useMarkRead();
  if (!user) return null;
  const unread = data?.unread ?? 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}>
          <Bell />
          {unread ? (
            <span className="absolute top-1 right-1 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-semibold text-white">
              {unread > 9 ? "9+" : unread}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0">
        <div className="flex items-center justify-between border-b px-4 py-2">
          <p className="text-sm font-medium">Notifications</p>
          {unread ? (
            <Button variant="ghost" size="sm" className="h-7" onClick={() => markRead.mutate(undefined)}>
              Mark all read
            </Button>
          ) : null}
        </div>
        <ul className="max-h-96 overflow-y-auto">
          {(data?.items ?? []).length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-muted-foreground">Nothing yet.</li>
          ) : (
            data!.items.map((n) => (
              <li key={n.id} className={cn("border-b last:border-0", !n.read && "bg-primary/5")}>
                <Link
                  href={n.link ?? "#"}
                  onClick={() => !n.read && markRead.mutate(n.id)}
                  className="grid grid-cols-[0.5rem_1fr] gap-3 px-4 py-3 hover:bg-muted/50"
                >
                  <span className={cn("mt-1.5 size-2 rounded-full", DOT[n.severity] ?? DOT.info)} />
                  <span className="grid gap-0.5">
                    <span className="text-sm font-medium">{n.title}</span>
                    <span className="text-sm text-muted-foreground">{n.body}</span>
                    <span className="text-xs text-muted-foreground">
                      {when.format(new Date(n.created_at))}
                      {n.emailed ? " · email copy (simulated)" : ""}
                    </span>
                  </span>
                </Link>
              </li>
            ))
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
