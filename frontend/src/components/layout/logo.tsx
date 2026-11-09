import Link from "next/link";

import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("tm-site-logo", className)}>
      <svg viewBox="0 0 24 24" className="size-5" aria-hidden fill="none">
        <circle cx="5" cy="17" r="2.5" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="19" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.6" />
        <path d="M7 15.5C10 13 12 11 16.8 8.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="0.1 3.4" />
      </svg>
      <span>{siteConfig.name}</span>
    </Link>
  );
}
