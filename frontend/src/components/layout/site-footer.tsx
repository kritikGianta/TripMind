import Link from "next/link";

import { siteConfig } from "@/config/site";

export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto grid max-w-6xl gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex sm:items-center sm:justify-between">
        <p>
          © {siteConfig.name}. {siteConfig.disclaimer}
        </p>
        <nav aria-label="Footer" className="flex gap-4">
          {siteConfig.nav.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-foreground">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
