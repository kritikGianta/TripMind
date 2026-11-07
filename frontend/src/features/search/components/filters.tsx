"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

import type { Schemas } from "@/lib/api/client";

import { formatMoney } from "../format";

type FacetOption = Schemas["FacetOption"];
type PriceRange = Schemas["PriceRange"];

/** Search state lives in the URL, so results are shareable and survive reloads and sign-in. */
export function useUrlState() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const update = useCallback(
    (changes: Record<string, string | string[] | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(changes)) {
        next.delete(key);
        if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
        else if (value !== null && value !== "") next.set(key, value);
      }
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [params, pathname, router],
  );
  return { params, update };
}

export function FilterGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="grid gap-2 border-b pb-4 last:border-0">
      <legend className="mb-1 text-sm font-medium">{title}</legend>
      {children}
    </fieldset>
  );
}

export function CheckboxFacet({
  name,
  options,
  selected,
  onChange,
  showPrice,
}: {
  name: string;
  options: FacetOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  showPrice?: boolean;
}) {
  if (!options.length) return <p className="text-xs text-muted-foreground">No options</p>;
  return (
    <div className="grid gap-2">
      {options.map((option) => {
        const id = `${name}-${option.value}`;
        const checked = selected.includes(option.value);
        return (
          <div key={option.value} className="flex items-center gap-2 text-sm">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={(state) =>
                onChange(state ? [...selected, option.value] : selected.filter((v) => v !== option.value))
              }
            />
            <Label htmlFor={id} className="flex-1 font-normal">
              {option.label} <span className="text-muted-foreground">({option.count})</span>
            </Label>
            {showPrice && option.min_price ? (
              <span className="text-xs text-muted-foreground tabular-nums">{formatMoney(option.min_price)}</span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function PriceFacet({
  range,
  value,
  onCommit,
  caption,
}: {
  range: PriceRange | null | undefined;
  value: number | null;
  onCommit: (max: number | null) => void;
  caption: string;
}) {
  if (!range) return <p className="text-xs text-muted-foreground">No prices</p>;
  const digits = 2;
  const min = Math.floor(range.min.amount_minor / 10 ** digits);
  const max = Math.ceil(range.max.amount_minor / 10 ** digits);
  if (max <= min) return null;
  const current = value ?? max;
  return (
    <div className="grid gap-2">
      <Slider
        min={min}
        max={max}
        step={Math.max(1, Math.round((max - min) / 100))}
        defaultValue={[current]}
        key={`${min}-${max}-${value}`}
        onValueCommit={([v]) => onCommit(v >= max ? null : v)}
        aria-label={caption}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{caption}</span>
        <span className="tabular-nums">
          up to {formatMoney({ amount_minor: current * 10 ** digits, currency: range.max.currency })}
        </span>
      </div>
    </div>
  );
}

export function SortBar<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Sort results" className="inline-flex rounded-lg border p-0.5">
      {options.map((option) => (
        <Button
          key={option.value}
          role="radio"
          aria-checked={value === option.value}
          size="sm"
          variant={value === option.value ? "secondary" : "ghost"}
          className="h-8"
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}
