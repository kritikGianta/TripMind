"use client";

import { useEffect, useRef } from "react";

import { homeCopy } from "@/content/home";
import { siteConfig } from "@/config/site";
import { DatasetLabel } from "@/features/meta/dataset-label";
import { setMotionChoice, useMotionChoice } from "@/features/motion/use-motion";

import { FilmDialog, HomeNav, HowItWorks } from "./chrome";
import { Confidence, Destinations, FinalCall, HomeFooter, JourneyMap, Proof, RouteCode, Ways } from "./journeys";
import { HomeProvider, Letters, type MediaFiles } from "./media";
import { CursorDot, SmoothScroll } from "./motion";
import { Hero, SearchSection, Statement, WorksWithoutAi } from "./opening";

import "./home.css";

export function HomeExperience({ media, fonts }: { media: MediaFiles; fonts: string }) {
  const motion = useMotionChoice();
  const root = useRef<HTMLDivElement>(null);
  const progress = useRef<HTMLDivElement>(null);

  // Fade and slide elements in once as they first appear. `data-ready` arms the hidden state only
  // now that scripts are running, so a script failure can never leave content invisible.
  useEffect(() => {
    const page = root.current;
    if (!page) return;
    page.setAttribute("data-ready", "");
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.setAttribute("data-in", "");
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px" },
    );
    page.querySelectorAll("[data-reveal]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  // How far down the page we are, for the progress line.
  useEffect(() => {
    let queued = false;
    const measure = () => {
      queued = false;
      const height = document.documentElement.scrollHeight - window.innerHeight;
      // Written to the line itself: on a page-wide element this would restyle the whole page each frame.
      progress.current?.style.setProperty("--page", (height > 0 ? window.scrollY / height : 0).toFixed(4));
    };
    const onScroll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(measure);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <HomeProvider media={media} fonts={fonts}>
      <div ref={root} className={`tm-home ${fonts}`} data-motion={motion}>
        <SmoothScroll enabled={motion === "full"} />
        <CursorDot enabled={motion === "full"} />
        <div ref={progress} className="tm-progress" aria-hidden />
        <HomeNav />
        <HowItWorks />
        <FilmDialog />
        <button
          type="button"
          className="tm-motion-switch"
          data-off={motion !== "full" || undefined}
          onClick={() => setMotionChoice(motion === "full" ? "reduced" : "full")}
        >
          {motion === "full" ? "Motion on" : "Motion off · turn on"}
        </button>
        <div className="tm-main">
          <Hero />
          <SearchSection />
          <Statement />
          <WorksWithoutAi />
          <Ways />
          <Confidence />
          <Destinations />
          <Proof />
          <RouteCode />
          <JourneyMap />
          <FinalCall />
        </div>
        <footer className="tm-lines tm-footer">
          <HomeFooter />
          <p className="tm-display tm-footer__word" aria-hidden>
            <Letters text={homeCopy.hero.wordmark} />
          </p>
          <div className="tm-footer__legal">
            <p className="tm-italic">{siteConfig.tagline}</p>
            <div>
              <p>
                © {siteConfig.name}. {siteConfig.disclaimer}
              </p>
              <DatasetLabel />
            </div>
          </div>
        </footer>
      </div>
    </HomeProvider>
  );
}
