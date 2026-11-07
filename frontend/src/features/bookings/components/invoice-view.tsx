"use client";

import { Printer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { siteConfig } from "@/config/site";
import { formatMoney } from "@/features/search/format";

import { useBooking } from "../api";

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Printable invoice and itinerary. Print or "Save as PDF" from the browser. */
export function InvoiceView() {
  const { id } = useParams<{ id: string }>();
  const { data: b, isPending } = useBooking(id);
  if (isPending || !b) return <Skeleton className="h-96 w-full" />;
  const paid = b.payments.find((p) => p.status === "succeeded");
  const refunded = b.refunds.reduce((n, r) => n + r.amount.amount_minor, 0);
  const subtotal = b.total.amount_minor + (b.discount?.amount_minor ?? 0);

  return (
    <div className="grid gap-6">
      <div className="flex justify-between gap-2 print:hidden">
        <Button asChild variant="ghost" size="sm">
          <Link href={`/bookings/${b.id}`}>Back to booking</Link>
        </Button>
        <Button size="sm" onClick={() => window.print()}>
          <Printer /> Print or save as PDF
        </Button>
      </div>
      <article className="grid gap-6 rounded-lg border bg-card p-8 text-sm print:border-0 print:p-0">
        <header className="flex flex-wrap justify-between gap-4">
          <div>
            <p className="text-xl font-semibold">{siteConfig.name}</p>
            <p className="text-muted-foreground">Booking confirmation and invoice</p>
          </div>
          <div className="text-right">
            <p className="font-medium">Reference {b.reference}</p>
            <p className="text-muted-foreground">Status: {b.status.replace("_", " ")}</p>
            {b.confirmed_at ? <p className="text-muted-foreground">Confirmed {when.format(new Date(b.confirmed_at))}</p> : null}
          </div>
        </header>

        <section>
          <p className="mb-1 font-medium">Travellers</p>
          <p>{b.travellers.map((t) => `${t.first_name} ${t.last_name}`).join(", ")}</p>
          <p className="text-muted-foreground">Contact: {b.contact_email}</p>
        </section>

        <table className="w-full">
          <thead className="border-b text-left text-xs text-muted-foreground">
            <tr>
              <th className="py-2 font-medium">Item</th>
              <th className="py-2 font-medium">Dates</th>
              <th className="py-2 font-medium">Status</th>
              <th className="py-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {b.items.map((item) => (
              <tr key={item.id} className="border-b align-top">
                <td className="py-2">
                  <p className="font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.subtitle}</p>
                </td>
                <td className="py-2">
                  {day.format(new Date(item.starts_at))} – {day.format(new Date(item.ends_at))}
                </td>
                <td className="py-2 capitalize">{item.status}</td>
                <td className="py-2 text-right tabular-nums">{formatMoney(item.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <section className="ml-auto grid w-full max-w-xs gap-1">
          <div className="flex justify-between">
            <span>Subtotal</span>
            <span className="tabular-nums">{formatMoney({ amount_minor: subtotal, currency: b.total.currency })}</span>
          </div>
          {b.discount ? (
            <div className="flex justify-between text-emerald-700 dark:text-emerald-400">
              <span>Promo {b.promo_code}</span>
              <span className="tabular-nums">−{formatMoney(b.discount)}</span>
            </div>
          ) : null}
          <div className="flex justify-between border-t pt-1 font-semibold">
            <span>Total charged</span>
            <span className="tabular-nums">{formatMoney(b.total)}</span>
          </div>
          {refunded ? (
            <div className="flex justify-between">
              <span>Refunded</span>
              <span className="tabular-nums">−{formatMoney({ amount_minor: refunded, currency: b.total.currency })}</span>
            </div>
          ) : null}
          {paid ? (
            <p className="text-xs text-muted-foreground">
              Paid by {paid.card_brand} ending {paid.card_last4}
            </p>
          ) : null}
        </section>

        <footer className="grid gap-1 border-t pt-4 text-xs text-muted-foreground">
          <p>Item amounts are in the supplier&apos;s currency; the total is in {b.total.currency}. {b.fx_note ?? ""}</p>
          <p>Taxes and fees are not included in the supplied data and are not shown separately.</p>
          <p>
            Demonstration document from a hackathon prototype: payments are simulated and this is not a tax invoice or a
            travel ticket.
          </p>
        </footer>
      </article>
    </div>
  );
}
