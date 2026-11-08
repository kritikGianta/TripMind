"use client";

import { homeCopy } from "@/content/home";
import { siteConfig } from "@/config/site";
import { DatasetLabel } from "@/features/meta/dataset-label";

import { FilmDialog, HomeNav, HowItWorks } from "./chrome";
import { Confidence, Destinations, FinalCall, HomeFooter, JourneyMap, Proof, RouteCode, Ways } from "./journeys";
import { HomeProvider, type MediaFiles } from "./media";
import { CursorDot, SmoothScroll } from "./motion";
import { Hero, SearchSection, Statement, WorksWithoutAi } from "./opening";

import "./home.css";

export function HomeExperience({ media, fonts }: { media: MediaFiles; fonts: string }) {
  return (
    <HomeProvider media={media} fonts={fonts}>
      <div className={`tm-home ${fonts}`}>
        <SmoothScroll />
        <CursorDot />
        <HomeNav />
        <HowItWorks />
        <FilmDialog />
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
            {homeCopy.hero.wordmark}
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
