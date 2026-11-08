"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/api/use-query";
import { AlertCircle, Check, Copy, Crown, Heart, ThumbsUp, Users, X } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { toQuery } from "@/features/search/api";
import { clockTime, formatDay, formatMoney } from "@/features/search/format";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type Group = Schemas["GroupOut"];
type GroupOption = Schemas["GroupOptionOut"];
type Vote = GroupOption["my_vote"];

const VOTES: Array<{ value: Exclude<Vote, "none">; label: string; icon: typeof Heart; active: string }> = [
  { value: "love", label: "Love", icon: Heart, active: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/40" },
  { value: "ok", label: "OK", icon: ThumbsUp, active: "bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/40" },
  { value: "no", label: "No", icon: X, active: "bg-destructive/15 text-destructive border-destructive/40" },
];

function useGroupMutation(groupId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ path, method, body }: { path: string; method: "PUT" | "POST"; body: unknown }) =>
      apiFetch<Group>(`/groups/${groupId}${path}`, { method, body }),
    onSuccess: (group) => client.setQueryData(["group", groupId], group),
  });
}

/** "Plan with friends" on a plan: creates (or reopens) the plan's group. */
export function ShareWithGroupButton({ planId }: { planId: string }) {
  const router = useRouter();
  const share = useMutation({
    mutationFn: () => apiFetch<Group>(`/plans/${planId}/group`, { method: "POST" }),
    onSuccess: (group) => router.push(`/groups/${group.id}`),
  });
  return (
    <Button variant="outline" onClick={() => share.mutate()} disabled={share.isPending}>
      <Users /> {share.isPending ? "Opening…" : "Plan with friends"}
    </Button>
  );
}

function OptionRow({ group, item, onVote, busy }: { group: Group; item: GroupOption; onVote: (v: Vote) => void; busy: boolean }) {
  const o = item.option;
  const leader = group.leader_option_id === o.id;
  const decided = group.decided_option_id === o.id;
  const checkout = `/checkout?${toQuery({
    flight: [o.outbound.id, o.inbound.id],
    adults: group.request.adults,
    room: o.hotel.cheapest_room.room_type_id,
    checkIn: o.stay.check_in,
    checkOut: o.stay.check_out,
    rooms: o.stay.rooms,
    guests: o.stay.guests,
  })}`;
  return (
    <Card className={cn("grid gap-3 p-4 md:grid-cols-[1fr_auto]", (leader || decided) && "ring-2 ring-primary")}>
      <div className="grid gap-1 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">#{item.position}</span>
          {decided ? <Badge>Chosen</Badge> : leader ? <Badge variant="secondary"><Crown className="size-3" /> Leading</Badge> : null}
          <span className="font-medium">{o.hotel.name}</span>
          <span className="text-muted-foreground">· planner rank #{o.rank}</span>
        </div>
        <p className="text-muted-foreground">
          Out {formatDay(o.outbound.legs[0].departure_local)} {clockTime(o.outbound.legs[0].departure_local)} ·
          back {formatDay(o.inbound.legs[0].departure_local)} {clockTime(o.inbound.legs[0].departure_local)} ·
          {" "}{o.stay.nights} nights · {o.confidence.level} confidence
        </p>
        <p>
          <span className="font-medium tabular-nums">≈ {formatMoney(item.per_person)}</span> per person ·{" "}
          <span className="text-muted-foreground">{formatMoney(o.total)} total</span>
        </p>
        <p className="text-xs text-muted-foreground">
          {item.love} love · {item.ok} OK · {item.no} no
          {item.over_budget_for.length ? ` · over budget for ${item.over_budget_for.join(", ")}` : ""}
        </p>
      </div>
      <div className="grid content-start justify-items-end gap-2">
        {group.status === "open" ? (
          <div className="flex gap-1" role="group" aria-label="Your vote">
            {VOTES.map(({ value, label, icon: Icon, active }) => (
              <Button key={value} size="sm" variant="outline" disabled={busy} aria-pressed={item.my_vote === value}
                className={cn(item.my_vote === value && active)}
                onClick={() => onVote(item.my_vote === value ? "none" : value)}>
                <Icon /> {label}
              </Button>
            ))}
          </div>
        ) : null}
        {decided && group.is_owner ? (
          <Button asChild>
            <Link href={checkout}>Book this trip</Link>
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

export function GroupView() {
  const { id } = useParams<{ id: string }>();
  const { data: group, error, isPending } = useQuery({
    queryKey: ["group", id],
    queryFn: () => apiFetch<Group>(`/groups/${id}`),
    refetchInterval: 15_000, // see friends' votes arrive
  });
  const act = useGroupMutation(id);
  // null = not edited yet, so the field shows the saved value.
  const [budgetDraft, setBudget] = useState<string | null>(null);
  const me = group?.members.find((m) => m.is_me);
  const budget = budgetDraft ?? (me?.max_budget_per_person ? String(me.max_budget_per_person) : "");

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error || !group) {
    return (
      <Alert variant="destructive">
        <AlertCircle />
        <AlertDescription>{errorMessage(error)}</AlertDescription>
      </Alert>
    );
  }
  const invite = typeof window === "undefined" ? "" : `${window.location.origin}/groups/join/${group.invite_code}`;
  const leader = group.options.find((o) => o.option.id === group.leader_option_id);

  return (
    <div className="grid gap-5">
      <div>
        <p className="text-sm text-muted-foreground">Group trip · {group.members.length} people</p>
        <h1 className="text-2xl font-semibold tracking-tight">{group.title}</h1>
      </div>
      {group.status === "decided" ? (
        <Alert>
          <Check className="text-emerald-600" />
          <AlertTitle>The group has chosen</AlertTitle>
          <AlertDescription>
            {group.is_owner ? "Book the chosen option below for everyone." : "The organiser will book it for the group."}
          </AlertDescription>
        </Alert>
      ) : (
        <Card className="grid gap-2 p-4 text-sm">
          <p className="font-medium">Current consensus{leader ? `: #${leader.position} ${leader.option.hotel.name}` : ""}</p>
          <p className="text-muted-foreground">{group.consensus}</p>
          <p className="text-xs text-muted-foreground">
            Love counts 2, OK 1, No is a veto. Options nobody vetoed and that fit everyone&apos;s budget come first.
          </p>
          {group.is_owner && leader ? (
            <Button className="w-fit" disabled={act.isPending}
              onClick={() => act.mutate({ path: "/decide", method: "POST", body: { option_id: leader.option.id } },
                { onSuccess: () => toast.success("Decision shared with the group.") })}>
              Confirm #{leader.position} for the group
            </Button>
          ) : null}
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="grid gap-2 p-4 text-sm">
          <p className="font-medium">Invite friends</p>
          <div className="flex gap-2">
            <Input readOnly value={invite} aria-label="Invite link" />
            <Button variant="outline" size="icon" aria-label="Copy invite link"
              onClick={() => void navigator.clipboard.writeText(invite).then(() => toast.success("Invite link copied"))}>
              <Copy />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">Anyone with a TripMind account and this link can join and vote.</p>
        </Card>
        <Card className="grid gap-2 p-4 text-sm">
          <p className="font-medium">Members</p>
          <ul className="grid gap-1">
            {group.members.map((m) => (
              <li key={m.user_id} className="flex justify-between gap-2">
                <span>
                  {m.name}{m.is_me ? " (you)" : ""}{m.role === "owner" ? " · organiser" : ""}
                </span>
                <span className="text-muted-foreground">
                  {m.votes_cast} votes{m.max_budget_per_person ? ` · max ₹${m.max_budget_per_person.toLocaleString("en-IN")}` : ""}
                </span>
              </li>
            ))}
          </ul>
          <form className="flex gap-2" onSubmit={(e) => {
            e.preventDefault();
            act.mutate({ path: "/me", method: "PUT", body: { max_budget_per_person: budget ? Number(budget) : null } });
          }}>
            <Input inputMode="numeric" placeholder="My max per person (₹)" aria-label="My maximum budget per person"
              value={budget} onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))} />
            <Button type="submit" variant="outline" disabled={act.isPending}>Save</Button>
          </form>
        </Card>
      </div>
      {act.error ? <p className="text-sm text-destructive">{errorMessage(act.error)}</p> : null}
      <div className="grid gap-3">
        {group.options.map((item) => (
          <OptionRow key={item.option.id} group={group} item={item} busy={act.isPending}
            onVote={(vote) => act.mutate({ path: `/votes/${item.option.id}`, method: "PUT", body: { vote } })} />
        ))}
      </div>
    </div>
  );
}

export function JoinGroupView() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const join = useMutation({
    mutationFn: () => apiFetch<Group>("/groups/join", { method: "POST", body: { invite_code: code } }),
    onSuccess: (group) => router.replace(`/groups/${group.id}`),
  });
  const { mutate } = join;
  useEffect(() => {
    mutate();
  }, [mutate]);
  return join.error ? (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertDescription>{errorMessage(join.error)}</AlertDescription>
    </Alert>
  ) : (
    <Skeleton className="h-40 w-full" />
  );
}
