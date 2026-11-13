import type { Metadata } from "next";
import { Cormorant_Garamond, Inter_Tight, Oswald } from "next/font/google";
import { Suspense } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { siteConfig } from "@/config/site";

import { Providers } from "./providers";
import "./globals.css";

const display = Oswald({ subsets: ["latin"], variable: "--tm-display" });
const serif = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--tm-serif",
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
});
const sans = Inter_Tight({ subsets: ["latin"], variable: "--tm-sans" });

export const metadata: Metadata = {
  title: { default: siteConfig.name, template: `%s · ${siteConfig.name}` },
  description: siteConfig.description,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${serif.variable} ${sans.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Providers>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
          >
            Skip to content
          </a>
          {/* The header reads the current path, which is request-time data on dynamic routes. */}
          <Suspense fallback={<div className="h-14 border-b" />}>
            <SiteHeader />
          </Suspense>
          <main id="main" className="flex flex-1 flex-col">
            {children}
          </main>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
