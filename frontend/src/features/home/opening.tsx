"use client";

import { Pause, Play } from "lucide-react";
import Image from "next/image";
import { Suspense, useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { homeCopy } from "@/content/home";
import { siteConfig } from "@/config/site";
import { AiSearch } from "@/features/ai/ai-search";
import { SearchPanel } from "@/features/search/components/search-panel";

import { Letters, Media, Rise, Scribble, useHome } from "./media";
import { useScrollProgress } from "./motion";

// Measured: only from here is the hero invisible behind the clouds at every window size.
const COVERED_AT = 0.95;

export function Hero() {
  const { setFilmOpen, media } = useHome();
  const [videoPaused, setVideoPaused] = useState(false);
  const pausedRef = useRef(false);
  useEffect(() => {
    pausedRef.current = videoPaused;
  }, [videoPaused]);
  const ref = useScrollProgress<HTMLElement>("pin", (p, el) => {
    el.toggleAttribute("data-past", p > 0.3);
    // Once the clouds have covered everything, stop drawing what nobody can see.
    const covered = p > COVERED_AT;
    if (covered !== el.hasAttribute("data-covered")) {
      el.toggleAttribute("data-covered", covered);
      const video = el.querySelector("video");
      if (covered) video?.pause();
      else if (!pausedRef.current) void video?.play().catch(() => {});
    }
  });
  return (
    <section ref={ref} className="tm-hero" aria-label="Welcome">
      <div className="tm-hero__stage">
        <Media slot="hero-film" priority paused={videoPaused} className="tm-hero__media" />
        <div className="tm-hero__scrim" />
        <h1 className="tm-hero__word tm-display" aria-label={homeCopy.hero.wordmark}>
          <Letters text={homeCopy.hero.wordmark} />
        </h1>
        <div className="tm-hero__mid">
          <p className="tm-italic tm-hero__tagline">{siteConfig.tagline}</p>
          <div className="tm-hero__dock">
            <AiSearch />
          </div>
          <div className="tm-hero__actions">
            {media["hero-film"] ? (
              <button
                type="button"
                className="tm-chip tm-chip--wide tm-chip--icon"
                aria-label={videoPaused ? "Play background video" : "Pause background video"}
                onClick={() => setVideoPaused(!videoPaused)}
              >
                {videoPaused ? <Play className="size-3 fill-current" aria-hidden /> : <Pause className="size-3 fill-current" aria-hidden />}
              </button>
            ) : null}
            <button type="button" className="tm-chip tm-chip--wide" data-cursor="Play" onClick={() => setFilmOpen(true)}>
              {homeCopy.hero.film} <Play className="size-3 fill-current" aria-hidden />
            </button>
          </div>
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

export function WorksWithoutAi() {
  const ref = useScrollProgress<HTMLElement>("pass");
  return (
    <section ref={ref} className="tm-lines tm-promise">
      <div className="tm-promise__copy" data-reveal>
        <h2 className="tm-label">{homeCopy.promise.label}</h2>
        <p>{homeCopy.promise.text}</p>
      </div>
      <div className="tm-media tm-promise__ridge tm-promise__ridge--back" aria-hidden>
        <Image src="/home/ridge-far.webp" alt="" fill sizes="130vw" />
      </div>
      <Media slot="ridge-landscape" sizes="118vw" className="tm-promise__ridge" />
    </section>
  );
}
