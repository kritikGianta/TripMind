"use client";

import Image from "next/image";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { homeCopy } from "@/content/home";
import { siteConfig } from "@/config/site";
import { SearchPanel } from "@/features/search/components/search-panel";

import { Letters, Media, Rise, Scribble, useHome } from "./media";
import { useScrollProgress } from "./motion";

// Measured: only from here is the hero invisible behind the clouds at every window size.
const COVERED_AT = 0.95;

export function Hero() {
  const ref = useScrollProgress<HTMLElement>("pin", (p, el) => {
    el.toggleAttribute("data-past", p > 0.3);
    // Once the clouds have covered everything, stop drawing what nobody can see.
    const covered = p > COVERED_AT;
    if (covered !== el.hasAttribute("data-covered")) {
      el.toggleAttribute("data-covered", covered);
      const video = el.querySelector("video");
      if (covered) video?.pause();
      else void video?.play().catch(() => {});
    }
  });
  return (
    <section ref={ref} className="tm-hero" aria-label="Welcome">
      <div className="tm-hero__stage">
        <Media slot="hero-film" priority className="tm-hero__media" />
        <div className="tm-hero__scrim" />
        <h1 className="tm-hero__word tm-display" aria-label={homeCopy.hero.wordmark}>
          <Letters text={homeCopy.hero.wordmark} />
        </h1>
        <div className="tm-hero__mid">
          <p className="tm-italic tm-hero__tagline">{siteConfig.tagline}</p>
        </div>
        <div className="tm-fog" aria-hidden>
          <i className="tm-fog__back" />
          <i className="tm-fog__front" />
        </div>
      </div>
    </section>
  );
}

export function SearchSection() {
  const ref = useScrollProgress<HTMLElement>("pass");
  return (
    <section ref={ref} id="search" className="tm-lines tm-search">
      <div className="tm-eyebrow">
        <Scribble />
        <p className="tm-italic">{homeCopy.search.label}</p>
      </div>
      <h2 className="tm-serif-h tm-serif-h--lg text-center" data-reveal="rise">
        <Rise text={homeCopy.search.heading} />
      </h2>
      <p className="mx-auto mt-4 max-w-md text-center text-sm text-[var(--ink-soft)]">{homeCopy.search.note}</p>
      <div className="tm-search__panel" data-reveal>
        <Suspense fallback={<Skeleton className="h-40 w-full" />}>
          <SearchPanel />
        </Suspense>
      </div>
    </section>
  );
}

export function Statement() {
  const ref = useScrollProgress<HTMLElement>("pass");
  const words = homeCopy.statement.text.split(" ");
  return (
    <section ref={ref} className="tm-lines tm-statement">
      <div className="tm-eyebrow tm-eyebrow--left">
        <Scribble />
        <p className="tm-italic">{homeCopy.statement.label}</p>
      </div>
      <p className="tm-statement__text">
        {words.map((word, index) => (
          <span key={`${word}-${index}`} className="tm-word" style={{ "--i": index / words.length } as React.CSSProperties}>
            {word}{" "}
          </span>
        ))}
      </p>
    </section>
  );
}

export function Ridge() {
  const ref = useScrollProgress<HTMLElement>("pass");
  return (
    <section ref={ref} className="tm-lines tm-promise" aria-hidden>
      <div className="tm-media tm-promise__ridge tm-promise__ridge--back" aria-hidden>
        <Image src="/home/ridge-far.webp" alt="" fill sizes="130vw" />
      </div>
      <Media slot="ridge-landscape" sizes="118vw" className="tm-promise__ridge" />
    </section>
  );
}
