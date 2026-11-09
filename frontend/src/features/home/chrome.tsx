"use client";

import { Menu as MenuIcon, Plus, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { homeCopy } from "@/content/home";
import { siteConfig } from "@/config/site";
import { UserMenu } from "@/features/auth/components/user-menu";
import { NotificationBell } from "@/features/recovery/components/notification-bell";

import { Media, useHome } from "./media";

function Mark() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" aria-hidden>
      <circle cx="5" cy="17" r="2.5" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="19" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M7 15.5C10 13 12 11 16.8 8.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="0.1 3.4" />
    </svg>
  );
}

/** Floating glass navigation: slips away on the way down, returns on the way up. */
export function HomeNav() {
  const { fonts, setHowOpen } = useHome();
  const nav = useRef<HTMLElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      if (Math.abs(y - last) < 6) return;
      nav.current?.toggleAttribute("data-hidden", y > last && y > 120);
      last = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <header ref={nav} className="tm-nav">
        <nav aria-label="Main" className="flex items-center gap-1">
          <button type="button" className="tm-chip" onClick={() => setMenuOpen(true)}>
            <MenuIcon className="size-3.5 md:hidden" aria-hidden /> Menu
          </button>
          <Link href="/flights" className="tm-chip tm-nav__wide">
            Flights
          </Link>
          <Link href="/stays" className="tm-chip tm-nav__wide">
            Stays
          </Link>
          <Link href="/about" className="tm-chip tm-nav__wider">
            About
          </Link>
        </nav>
        <Link href="/" className="tm-nav__logo" aria-label={`${siteConfig.name} home`}>
          <Mark />
          <span>{siteConfig.name}</span>
        </Link>
        <div className="flex items-center justify-end gap-1">
          <div className="tm-nav__session">
            <NotificationBell />
            <UserMenu />
          </div>
          <Link href="/plan" className="tm-chip tm-chip--accent">
            Plan a trip
          </Link>
        </div>
      </header>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className={`${fonts} tm-menu`}>
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SheetDescription className="sr-only">Where you can go on {siteConfig.name}</SheetDescription>
          <div className="grid gap-8 overflow-y-auto">
            <Link href="/" className="tm-menu__link" onClick={() => setMenuOpen(false)}>
              Home
            </Link>
            {homeCopy.menu.map((group) => (
              <div key={group.title} className="grid gap-2">
                <p className="tm-italic text-lg text-[var(--ink-soft)]">{group.title}</p>
                {group.links.map((link) => (
                  <Link key={link.href} href={link.href} className="tm-menu__link" onClick={() => setMenuOpen(false)}>
                    {link.label}
                  </Link>
                ))}
              </div>
            ))}
            <button
              type="button"
              className="tm-menu__link text-left"
              onClick={() => {
                setMenuOpen(false);
                setHowOpen(true);
              }}
            >
              {homeCopy.how.heading}
            </button>
            <div className="sm:hidden">
              <UserMenu />
            </div>
          </div>
          <Link href="/plan" className="tm-menu__cta" onClick={() => setMenuOpen(false)}>
            {homeCopy.cta.action}
          </Link>
        </SheetContent>
      </Sheet>
    </>
  );
}

/** The accent tab on the right edge, and the drawer it opens. Shown past the hero, before the footer. */
export function HowItWorks() {
  const { fonts, howOpen, setHowOpen } = useHome();
  const tab = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onScroll = () => {
      const fromBottom = document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
      tab.current?.toggleAttribute("data-shown", window.scrollY > window.innerHeight * 0.7 && fromBottom > window.innerHeight * 1.2);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <button ref={tab} type="button" className="tm-how-tab" onClick={() => setHowOpen(true)}>
        <span>{homeCopy.how.tab}</span>
        <Plus className="size-3.5" aria-hidden />
      </button>
      <Sheet open={howOpen} onOpenChange={setHowOpen}>
        <SheetContent side="right" showCloseButton={false} className={`${fonts} tm-how`}>
          <button type="button" className="tm-how-tab tm-how-tab--close" data-shown onClick={() => setHowOpen(false)}>
            <span>Close</span>
            <X className="size-3.5" aria-hidden />
          </button>
          <div className="grid gap-3 overflow-y-auto p-6 md:p-12">
            <SheetTitle className="tm-serif-h mb-6 font-normal">{homeCopy.how.heading}</SheetTitle>
            <SheetDescription className="sr-only">The four steps of a booking on {siteConfig.name}</SheetDescription>
            {homeCopy.how.steps.map((step, index) => (
              <div key={step.name} className="tm-how__step bg-[var(--stone-2)] p-5 md:p-6" style={{ "--i": index } as React.CSSProperties}>
                <p className="tm-italic mb-2 text-xl text-[var(--ink)]">{step.name}</p>
                <p className="text-sm leading-relaxed text-[var(--ink-soft)]">{step.text}</p>
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

export function FilmDialog() {
  const { fonts, filmOpen, setFilmOpen } = useHome();
  return (
    <Dialog open={filmOpen} onOpenChange={setFilmOpen}>
      <DialogContent className={`${fonts} tm-film`}>
        <DialogTitle className="sr-only">{homeCopy.hero.film}</DialogTitle>
        <DialogDescription className="sr-only">The {siteConfig.name} film</DialogDescription>
        {filmOpen ? <Media slot="brand-film" film /> : null}
      </DialogContent>
    </Dialog>
  );
}
