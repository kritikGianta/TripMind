"use client";

import { ChevronDown, ChevronUp, Maximize2, Minimize2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type DeckSlide = { id: string; title: string; content: ReactNode };

const NEXT_KEYS = new Set(["ArrowDown", "ArrowRight", "PageDown", " "]);
const PREV_KEYS = new Set(["ArrowUp", "ArrowLeft", "PageUp"]);

function isTyping(target: EventTarget | null) {
  return target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
}

/**
 * Presentation deck: one slide per screen with scroll snapping.
 * Keys: ← → ↑ ↓ / Space / PageUp / PageDown move, Home / End jump, F toggles full screen.
 * The URL hash tracks the current slide, so a specific slide can be linked or reopened.
 */
export function Deck({ slides }: { slides: DeckSlide[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [current, setCurrent] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);

  const goTo = useCallback(
    (index: number) => {
      const clamped = Math.max(0, Math.min(slides.length - 1, index));
      document.getElementById(slides[clamped].id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [slides],
  );

  const toggleFullscreen = useCallback(() => {
    const element = containerRef.current;
    if (!element) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void element.requestFullscreen?.();
  }, []);

  // Track the visible slide and mirror it into the URL hash.
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const index = slides.findIndex((slide) => slide.id === entry.target.id);
          if (index >= 0) {
            setCurrent(index);
            window.history.replaceState(null, "", `#${slides[index].id}`);
          }
        }
      },
      { root, threshold: 0.55 },
    );
    slides.forEach((slide) => {
      const node = document.getElementById(slide.id);
      if (node) observer.observe(node);
    });
    return () => observer.disconnect();
  }, [slides]);

  // Open at the slide named in the URL.
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id) document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      if (NEXT_KEYS.has(event.key)) goTo(current + 1);
      else if (PREV_KEYS.has(event.key)) goTo(current - 1);
      else if (event.key === "Home") goTo(0);
      else if (event.key === "End") goTo(slides.length - 1);
      else if (event.key.toLowerCase() === "f") toggleFullscreen();
      else return;
      event.preventDefault();
    };
    const onFullscreen = () => setFullscreen(Boolean(document.fullscreenElement));
    window.addEventListener("keydown", onKey);
    document.addEventListener("fullscreenchange", onFullscreen);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("fullscreenchange", onFullscreen);
    };
  }, [current, goTo, toggleFullscreen, slides.length]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative snap-y snap-mandatory overflow-y-auto bg-background",
        fullscreen ? "h-screen" : "h-[calc(100dvh-3.5rem)]",
      )}
    >
      {slides.map((slide, index) => (
        <section
          key={slide.id}
          id={slide.id}
          aria-label={`Slide ${index + 1} of ${slides.length}: ${slide.title}`}
          className="flex min-h-full snap-start items-center"
        >
          <div className="mx-auto w-full max-w-6xl px-6 py-12 md:px-10">{slide.content}</div>
        </section>
      ))}

      <div className="sticky bottom-0 z-10 h-0">
        <div className="absolute right-4 bottom-4 flex items-center gap-2 rounded-full border bg-background/90 p-1 pl-3 shadow-sm backdrop-blur">
          <span className="text-xs tabular-nums text-muted-foreground" aria-live="polite">
            {current + 1} / {slides.length}
          </span>
          <Button size="icon" variant="ghost" className="size-8" onClick={() => goTo(current - 1)} disabled={current === 0} aria-label="Previous slide">
            <ChevronUp />
          </Button>
          <Button size="icon" variant="ghost" className="size-8" onClick={() => goTo(current + 1)} disabled={current === slides.length - 1} aria-label="Next slide">
            <ChevronDown />
          </Button>
          <Button size="sm" variant="secondary" className="h-8 rounded-full" onClick={toggleFullscreen}>
            {fullscreen ? <Minimize2 /> : <Maximize2 />}
            {fullscreen ? "Exit" : "Present"}
          </Button>
        </div>
        <div className="absolute bottom-0 left-0 h-0.5 bg-primary transition-[width] duration-300" style={{ width: `${((current + 1) / slides.length) * 100}%` }} />
      </div>
    </div>
  );
}
