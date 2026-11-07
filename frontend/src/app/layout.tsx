import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { AssistantLauncher } from "@/features/ai/assistant-launcher";
import { siteConfig } from "@/config/site";

import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: siteConfig.name, template: `%s · ${siteConfig.name}` },
  description: siteConfig.description,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
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
          <Suspense fallback={null}>
            <AssistantLauncher />
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
