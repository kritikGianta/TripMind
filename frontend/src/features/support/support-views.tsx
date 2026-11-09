"use client";

import { ArrowLeft, LifeBuoy, Plus, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/features/auth/components/form-error";
import { useTrips } from "@/features/bookings/api";

import {
  CATEGORY_LABELS,
  STATUS_LABELS,
  TOPIC_SUBJECTS,
  useAdminTickets,
  useAgentReply,
  useCloseTicket,
  useCreateTicket,
  useMyTickets,
  useReply,
  useTicket,
  useUpdateTicket,
  type Ticket,
  type TicketSummary,
  type TicketUpdate,
} from "./api";

const stamp = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function TicketStatus({ status }: { status: string }) {
  const tone = status === "resolved" || status === "closed" ? "outline" : status === "waiting_on_traveller" ? "default" : "secondary";
  return <Badge variant={tone}>{STATUS_LABELS[status] ?? status}</Badge>;
}

function TicketRow({ ticket, href, showEmail }: { ticket: TicketSummary; href: string; showEmail?: boolean }) {
  return (
    <Link href={href} className="grid gap-1 border-t py-3 transition-colors first:border-0 hover:bg-muted/60 sm:grid-cols-[1fr_auto] sm:items-center sm:px-2">
      <div className="min-w-0">
        <p className="truncate font-medium">{ticket.subject}</p>
        <p className="text-sm text-muted-foreground">
          {ticket.reference} · {ticket.category_label}
          {showEmail && ticket.traveller_email ? ` · ${ticket.traveller_email}` : ""}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {ticket.priority === "high" ? <Badge variant="destructive">Urgent</Badge> : null}
        <TicketStatus status={ticket.status} />
        <span>{stamp.format(new Date(ticket.updated_at))}</span>
      </div>
    </Link>
  );
}

export function TicketsView() {
  const { data, isPending } = useMyTickets();
  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Your requests</CardTitle>
          <CardDescription>We file each request by topic, and mark it urgent when your trip is close.</CardDescription>
        </div>
        <Button asChild>
          <Link href="/support/new">
            <Plus /> New request
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-24 w-full" /> : null}
        {data && data.items.length === 0 ? (
          <div className="grid justify-items-center gap-2 py-8 text-center text-muted-foreground">
            <LifeBuoy className="size-8" aria-hidden />
            <p>No requests yet. The assistant can answer most questions straight away.</p>
          </div>
        ) : null}
        {data?.items.map((ticket) => <TicketRow key={ticket.id} ticket={ticket} href={`/support/${ticket.id}`} />)}
      </CardContent>
    </Card>
  );
}

export function NewTicketView() {
  const params = useSearchParams();
  const router = useRouter();
  const topic = params.get("topic") ?? "";
  const presetBooking = params.get("booking") ?? "none";
  const [subject, setSubject] = useState(TOPIC_SUBJECTS[topic] ?? "");
  const [message, setMessage] = useState("");
  const [booking, setBooking] = useState(presetBooking);
  const create = useCreateTicket();
  const trips = useTrips();
  const bookings = trips.data?.items.flatMap((trip) => trip.bookings.map((b) => ({ id: b.id, label: `${b.reference} · ${trip.title}` }))) ?? [];

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate(
      { subject: subject.trim(), message: message.trim(), booking_id: booking === "none" ? null : booking },
      {
        onSuccess: (ticket) => {
          toast.success(`Request ${ticket.reference} received.`);
          router.push(`/support/${ticket.id}`);
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>What do you need help with?</CardTitle>
        <CardDescription>Don&apos;t include card numbers or passwords. A person reads every request.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="ticket-subject">Subject</Label>
            <Input id="ticket-subject" value={subject} maxLength={140} onChange={(e) => setSubject(e.target.value)} required minLength={4} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="ticket-booking">Which booking is this about?</Label>
            <Select value={booking} onValueChange={setBooking}>
              <SelectTrigger id="ticket-booking" className="w-full">
                <SelectValue placeholder="Not about a booking" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Not about a booking</SelectItem>
                {bookings.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="ticket-message">Your message</Label>
            <Textarea id="ticket-message" rows={6} value={message} maxLength={4000} onChange={(e) => setMessage(e.target.value)} required minLength={10} />
            <p className="text-xs text-muted-foreground">At least 10 characters.</p>
          </div>
          <FormError error={create.error} />
          <Button type="submit" className="w-fit" disabled={create.isPending}>
            <Send /> {create.isPending ? "Sending…" : "Send request"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Thread({ ticket }: { ticket: Ticket }) {
  return (
    <ol className="grid gap-3">
      {ticket.messages.map((message) => {
        const fromTraveller = message.author_role === "traveler" || message.author_role === "traveller";
        return (
          <li key={message.id} className={`max-w-[85%] rounded-sm p-3 text-sm ${fromTraveller ? "justify-self-end bg-primary text-primary-foreground" : "bg-muted"}`}>
            <p className="whitespace-pre-wrap break-words">{message.body}</p>
            <p className="mt-1 text-xs opacity-70">
              {fromTraveller ? "You" : "TripMind support"} · {stamp.format(new Date(message.created_at))}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

function FiledUnder({ ticket }: { ticket: Ticket }) {
  return (
    <p className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
      <Sparkles className="size-3.5" aria-hidden />
      Filed under <span className="font-medium text-foreground">{ticket.category_label}</span>
      {ticket.category_source === "agent" ? " by an agent" : " automatically"}
      {ticket.priority === "high" ? <Badge variant="destructive">Urgent</Badge> : null}
    </p>
  );
}

export function TicketView() {
  const { id } = useParams<{ id: string }>();
  const { data: ticket, error, isPending } = useTicket(id);
  const reply = useReply(id);
  const close = useCloseTicket(id);
  const [body, setBody] = useState("");

  if (isPending) return <Skeleton className="h-72 w-full" />;
  if (error || !ticket) return <FormError error={error} />;
  const closed = ticket.status === "closed";

  return (
    <div className="grid gap-4">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link href="/support">
          <ArrowLeft /> All requests
        </Link>
      </Button>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>{ticket.subject}</CardTitle>
            <TicketStatus status={ticket.status} />
          </div>
          <CardDescription>
            {ticket.reference}
            {ticket.booking_reference ? ` · booking ${ticket.booking_reference}` : ""}
          </CardDescription>
          <FiledUnder ticket={ticket} />
        </CardHeader>
        <CardContent className="grid gap-4">
          <Thread ticket={ticket} />
          {closed ? (
            <p className="text-sm text-muted-foreground">This request is closed. Start a new one if you need more help.</p>
          ) : (
            <form
              className="grid gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (body.trim()) reply.mutate(body.trim(), { onSuccess: () => setBody("") });
              }}
            >
              <Label htmlFor="ticket-reply">Add a message</Label>
              <Textarea id="ticket-reply" rows={3} value={body} maxLength={4000} onChange={(e) => setBody(e.target.value)} />
              <FormError error={reply.error ?? close.error} />
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={reply.isPending || !body.trim()}>
                  <Send /> Send
                </Button>
                <Button type="button" variant="outline" disabled={close.isPending} onClick={() => close.mutate()}>
                  Close request
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const ANY = "any";

export function AdminTicketsView() {
  const [status, setStatus] = useState(ANY);
  const [category, setCategory] = useState(ANY);
  const { data, isPending } = useAdminTickets(status === ANY ? null : status, category === ANY ? null : category);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Support queue</CardTitle>
        <CardDescription>
          {data ? Object.entries(data.counts).map(([key, count]) => `${STATUS_LABELS[key] ?? key}: ${count}`).join(" · ") : "Loading…"}
        </CardDescription>
        <div className="mt-2 flex flex-wrap gap-2">
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger aria-label="Filter by status" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>All statuses</SelectItem>
              {Object.entries(STATUS_LABELS).map(([key, label]) => (
                <SelectItem key={key} value={key}>
                  {key === "waiting_on_traveller" ? "Waiting on traveller" : label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger aria-label="Filter by category" className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>All categories</SelectItem>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <SelectItem key={key} value={key}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-24 w-full" /> : null}
        {data && data.items.length === 0 ? <p className="py-6 text-center text-muted-foreground">Nothing in this queue.</p> : null}
        {data?.items.map((ticket) => <TicketRow key={ticket.id} ticket={ticket} href={`/admin/support/${ticket.id}`} showEmail />)}
      </CardContent>
    </Card>
  );
}

export function AdminTicketView() {
  const { id } = useParams<{ id: string }>();
  const { data: ticket, error, isPending } = useTicket(id, true);
  const reply = useAgentReply(id);
  const update = useUpdateTicket(id);
  const [body, setBody] = useState("");
  const [after, setAfter] = useState<"waiting_on_traveller" | "resolved">("waiting_on_traveller");

  if (isPending) return <Skeleton className="h-72 w-full" />;
  if (error || !ticket) return <FormError error={error} />;

  return (
    <div className="grid gap-4">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link href="/admin/support">
          <ArrowLeft /> Back to the queue
        </Link>
      </Button>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>{ticket.subject}</CardTitle>
            <Badge variant="secondary">{STATUS_LABELS[ticket.status] ?? ticket.status}</Badge>
          </div>
          <CardDescription>
            {ticket.reference}
            {ticket.booking_reference ? ` · booking ${ticket.booking_reference}` : ""} · filed by {ticket.category_source}, confidence{" "}
            {Math.round(ticket.confidence * 100)}%
          </CardDescription>
          <div className="mt-2 flex flex-wrap gap-2">
            <Select value={ticket.category} onValueChange={(value) => update.mutate({ category: value as TicketUpdate["category"] })}>
              <SelectTrigger aria-label="Category" className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={ticket.priority} onValueChange={(value) => update.mutate({ priority: value as "normal" | "high" })}>
              <SelectTrigger aria-label="Priority" className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="high">Urgent</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" disabled={update.isPending} onClick={() => update.mutate({ status: "closed" })}>
              Close
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          <ol className="grid gap-3">
            {ticket.messages.map((message) => (
              <li key={message.id} className={`max-w-[85%] rounded-sm p-3 text-sm ${message.author_role === "admin" || message.author_role === "agent" ? "justify-self-end bg-primary text-primary-foreground" : "bg-muted"}`}>
                <p className="whitespace-pre-wrap break-words">{message.body}</p>
                <p className="mt-1 text-xs opacity-70">
                  {message.author_role} · {stamp.format(new Date(message.created_at))}
                </p>
              </li>
            ))}
          </ol>
          <form
            className="grid gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (body.trim()) reply.mutate({ body: body.trim(), status: after }, { onSuccess: () => setBody("") });
            }}
          >
            <Label htmlFor="agent-reply">Reply to the traveller</Label>
            <Textarea id="agent-reply" rows={3} value={body} maxLength={4000} onChange={(e) => setBody(e.target.value)} />
            <FormError error={reply.error ?? update.error} />
            <div className="flex flex-wrap items-center gap-2">
              <Select value={after} onValueChange={(value) => setAfter(value as typeof after)}>
                <SelectTrigger aria-label="After sending" className="w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="waiting_on_traveller">Then wait for the traveller</SelectItem>
                  <SelectItem value="resolved">Then mark resolved</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" disabled={reply.isPending || !body.trim()}>
                <Send /> Send reply
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
