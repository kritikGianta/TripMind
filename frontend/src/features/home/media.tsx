"use client";

import Image from "next/image";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { homeMedia, type MediaSlot } from "@/content/home";

export type MediaFile = { src: string; poster?: string };
export type MediaFiles = Partial<Record<MediaSlot, MediaFile>>;

type HomeState = {
  media: MediaFiles;
  /** next/font class names: dialogs render outside the page, so they need them too. */
  fonts: string;
  filmOpen: boolean;
  setFilmOpen: (open: boolean) => void;
  howOpen: boolean;
  setHowOpen: (open: boolean) => void;
};

const HomeContext = createContext<HomeState | null>(null);

export function useHome() {
  const state = useContext(HomeContext);
  if (!state) throw new Error("useHome must be used inside HomeProvider");
  return state;
}

export function HomeProvider({ media, fonts, children }: { media: MediaFiles; fonts: string; children: ReactNode }) {
  const [filmOpen, setFilmOpen] = useState(false);
  const [howOpen, setHowOpen] = useState(false);
  return (
    <HomeContext.Provider value={{ media, fonts, filmOpen, setFilmOpen, howOpen, setHowOpen }}>{children}</HomeContext.Provider>
  );
}

function LoopingVideo({ file }: { file: MediaFile }) {
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) video.current?.pause();
  }, []);
  return <video ref={video} className="tm-fill" src={file.src} poster={file.poster} autoPlay muted loop playsInline preload="metadata" aria-hidden />;
}

/**
 * One photo or video on the home page. Until `public/home/<slot>.<ext>` exists it paints a tinted
 * placeholder naming the slot, so the page can be judged and animated with no assets at all.
 */
export function Media({
  slot,
  sizes = "100vw",
  priority,
  film,
  className,
}: {
  slot: MediaSlot;
  sizes?: string;
  priority?: boolean;
  /** Playable with sound and controls, instead of a silent loop. */
  film?: boolean;
  className?: string;
}) {
  const info = homeMedia[slot];
  const file = useHome().media[slot];
  const classes = `tm-media ${className ?? ""}`;

  if (!file) {
    return (
      <div className={`${classes} tm-placeholder`} style={{ background: info.tone }} role="img" aria-label={info.alt} title={info.brief}>
        <span>
          {info.kind} · {slot}
        </span>
      </div>
    );
  }
  if (info.kind === "video") {
    return (
      <div className={classes}>
        {film ? (
          <video className="tm-fill" src={file.src} poster={file.poster} controls playsInline preload="metadata" />
        ) : (
          <LoopingVideo file={file} />
        )}
      </div>
    );
  }
  return (
    <div className={classes}>
      <Image src={file.src} alt={info.alt} fill sizes={sizes} priority={priority} className="object-cover" />
    </div>
  );
}

/** A hand-drawn flight path that draws itself as its section scrolls past. */
export function Scribble({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 60" fill="none" className={`tm-scribble ${className ?? ""}`} aria-hidden>
      <path
        pathLength={1}
        d="M2 44C42 18 96 6 136 12c30 5 34 26 8 30-24 4-40-14-14-26 44-20 110-10 188 18"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
      />
    </svg>
  );
}
