"use client";

import { Building2, MapPin, PlaneTakeoff } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { useLocations, type LocationKind } from "../api";

export type PickedLocation = { value: string; label: string };

function useDebounced<T>(value: T, ms: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

/** Type-ahead for airports (flights) or cities (stays), backed by /locations. */
export function LocationPicker({
  id,
  kind,
  value,
  onChange,
  placeholder,
  icon = kind === "airport" ? PlaneTakeoff : Building2,
  invalid,
}: {
  id: string;
  kind: LocationKind;
  value: PickedLocation | null;
  onChange: (value: PickedLocation) => void;
  placeholder: string;
  icon?: typeof MapPin;
  invalid?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const q = useDebounced(text, 150);
  const { data, isFetching } = useLocations(q, kind);
  const Icon = icon;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={invalid || undefined}
          className={cn("h-11 w-full justify-start gap-2 font-normal", !value && "text-muted-foreground")}
        >
          <Icon className="size-4 shrink-0 opacity-60" aria-hidden />
          <span className="truncate">{value?.label ?? placeholder}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-72 p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            value={text}
            onValueChange={setText}
            placeholder={kind === "airport" ? "City or airport code" : "City"}
          />
          <CommandList>
            <CommandEmpty>{isFetching ? "Searching…" : "No matches in this dataset."}</CommandEmpty>
            <CommandGroup>
              {(data?.items ?? []).map((item) => (
                <CommandItem
                  key={item.value}
                  value={item.value}
                  onSelect={() => {
                    onChange({
                      value: item.value,
                      label: item.kind === "airport" ? `${item.city_name} (${item.code})` : item.name,
                    });
                    setOpen(false);
                    setText("");
                  }}
                >
                  <MapPin className="opacity-60" aria-hidden />
                  <div className="grid">
                    <span>{item.kind === "airport" ? `${item.city_name} (${item.code})` : item.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {item.kind === "airport" ? item.name : item.country}
                    </span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
