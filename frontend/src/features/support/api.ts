"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { toQuery } from "@/features/search/api";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { useQuery } from "@/lib/api/use-query";

export type Ticket = Schemas["TicketOut"];
export type TicketSummary = Schemas["TicketSummaryOut"];
export type TicketUpdate = Schemas["TicketUpdateIn"];

const LIST_KEY = ["support", "tickets"] as const;

export function useMyTickets() {
  return useQuery({ queryKey: LIST_KEY, queryFn: () => apiFetch<Schemas["TicketListOut"]>("/support/tickets") });
}

export function useTicket(id: string, admin = false) {
  return useQuery({
    queryKey: ["support", admin ? "admin" : "mine", id],
    queryFn: () => apiFetch<Ticket>(`${admin ? "/admin" : ""}/support/tickets/${id}`),
  });
}

export function useCreateTicket() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["TicketIn"]) => apiFetch<Ticket>("/support/tickets", { method: "POST", body }),
    onSettled: () => void client.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useReply(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: string) =>
      apiFetch<Ticket>(`/support/tickets/${id}/messages`, { method: "POST", body: { body } }),
    onSuccess: (ticket) => client.setQueryData(["support", "mine", id], ticket),
    onSettled: () => void client.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useCloseTicket(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<Ticket>(`/support/tickets/${id}/close`, { method: "POST" }),
    onSuccess: (ticket) => client.setQueryData(["support", "mine", id], ticket),
    onSettled: () => void client.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useAdminTickets(status: string | null, category: string | null) {
  return useQuery({
    queryKey: ["support", "admin", "list", status, category],
    queryFn: () => apiFetch<Schemas["TicketListOut"]>(`/admin/support/tickets?${toQuery({ status, category })}`),
  });
}

export function useAgentReply(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Schemas["AgentReplyIn"]) =>
      apiFetch<Ticket>(`/admin/support/tickets/${id}/messages`, { method: "POST", body }),
    onSuccess: (ticket) => client.setQueryData(["support", "admin", id], ticket),
    onSettled: () => void client.invalidateQueries({ queryKey: ["support", "admin", "list"] }),
  });
}

export function useUpdateTicket(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: TicketUpdate) =>
      apiFetch<Ticket>(`/admin/support/tickets/${id}`, { method: "PATCH", body }),
    onSuccess: (ticket) => client.setQueryData(["support", "admin", id], ticket),
    onSettled: () => void client.invalidateQueries({ queryKey: ["support", "admin", "list"] }),
  });
}

export const CATEGORY_LABELS: Record<string, string> = {
  baggage_seats: "Baggage and seats",
  cancellation_refund: "Cancellation and refund",
  change_booking: "Changing a booking",
  check_in_boarding: "Check-in and boarding",
  existing_booking: "An existing booking",
  flight_status: "Flight status",
  human_agent: "Talk to a person",
  insurance: "Insurance",
  new_booking: "A new booking",
  other: "Something else",
};

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  waiting_on_traveller: "Waiting on you",
  resolved: "Resolved",
  closed: "Closed",
};

/** Wording for the subject when the assistant sends someone here with a topic. */
export const TOPIC_SUBJECTS: Record<string, string> = {
  human_agent: "I would like to talk to a person",
  cancellation_refund: "Help with a cancellation or refund",
  change_booking: "Help changing my booking",
};
