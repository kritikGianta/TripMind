import Link from "next/link";

import { siteConfig } from "@/config/site";
import { DatasetLabel } from "@/features/meta/dataset-label";

export function SiteFooter() {
  return (
    <footer className="tm-site-footer print:hidden">
      <div className="mx-auto grid max-w-[72rem] gap-5 px-4 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <p className="tm-site-footer__word">{siteConfig.name}</p>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium">
            {siteConfig.nav.map((item) => (
              <Link key={item.href} href={item.href} className="hover:underline">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="grid gap-1 border-t border-current/15 pt-3 text-xs text-[#596278]">
          <p>
            © {siteConfig.name}. {siteConfig.disclaimer}
          </p>
          <DatasetLabel />
        </div>
      </div>
    </footer>
  );
}
