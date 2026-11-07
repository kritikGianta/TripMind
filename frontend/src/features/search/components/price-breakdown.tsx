"use client";

import { Info } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { PriceLedger } from "../api";
import { formatMoney } from "../format";

/** The headline price, plus the ledger behind it. Unknown amounts are listed, never hidden. */
export function PriceBreakdown({ ledger, caption }: { ledger: PriceLedger; caption?: string }) {
  const display = ledger.display_total;
  return (
    <div className="grid justify-items-end gap-0.5 text-right">
      <div className="flex items-center gap-1">
        <span className="text-xl font-semibold tabular-nums">
          {display ? `${ledger.converted ? "≈ " : ""}${formatMoney(display)}` : "Price not provided"}
        </span>
        <Popover>
          <PopoverTrigger className="rounded p-0.5 text-muted-foreground hover:text-foreground" aria-label="Price breakdown">
            <Info className="size-4" />
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 text-sm">
            <p className="mb-2 font-medium">Price breakdown</p>
            <ul className="grid gap-1.5">
              {ledger.lines.map((line) => (
                <li key={line.label} className="flex justify-between gap-4">
                  <span className="text-muted-foreground">{line.label}</span>
                  <span className="tabular-nums">{line.amount ? formatMoney(line.amount) : (line.note ?? "—")}</span>
                </li>
              ))}
            </ul>
            {ledger.total || ledger.display_total ? (
              <div className="mt-2 flex justify-between border-t pt-2 font-medium">
                <span>Total shown</span>
                <span className="tabular-nums">
                  {ledger.total ? formatMoney(ledger.total) : formatMoney(ledger.display_total)}
                </span>
              </div>
            ) : null}
            {ledger.converted && ledger.display_total ? (
              <p className="mt-2 text-xs text-muted-foreground">
                ≈ {formatMoney(ledger.display_total)}. {ledger.fx_note}
              </p>
            ) : null}
            {!ledger.complete ? (
              <p className="mt-2 text-xs text-muted-foreground">
                The total excludes amounts the supplied data does not contain.
              </p>
            ) : null}
          </PopoverContent>
        </Popover>
      </div>
      {caption ? <span className="text-xs text-muted-foreground">{caption}</span> : null}
      {!ledger.complete && display ? <span className="text-xs text-muted-foreground">+ taxes and fees not included</span> : null}
    </div>
  );
}
