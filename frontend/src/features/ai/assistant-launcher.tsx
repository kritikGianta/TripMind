"use client";

import { usePathname } from "next/navigation";

import { AssistantWidget } from "./assistant-widget";

/** The assistant on every page except the presentation deck, which uses that corner. */
export function AssistantLauncher() {
  const pathname = usePathname();
  return pathname.startsWith("/about") ? null : <AssistantWidget />;
}
