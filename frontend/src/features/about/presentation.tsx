"use client";

import Lenis from "lenis";
import { ChevronDown, ChevronUp, Maximize2, Menu as MenuIcon, Minimize2, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import * as about from "@/content/about";

import { Scenes } from "./scenes";

import "./about.css";

const CHOICE_KEY = "tm-about-motion";
const SEEN_KEY = "tm-about-opened";
const CALM = "(prefers-reduced-motion: reduce)";
const SMALL = "(max-width: 900px), (max-height: 560px)";
const CHOICE_EVENT = "tm-about-motion";
const GLIDE_SECONDS = 1.3;

function storedChoice() {
  try {
    return window.localStorage.getItem(CHOICE_KEY);
  } catch {
    return null;
  }
}

function subscribe(onChange: () => void) {
  const queries = [window.matchMedia(CALM), window.matchMedia(SMALL)];
  queries.forEach((query) => query.addEventListener("change", onChange));
  window.addEventListener(CHOICE_EVENT, onChange);
  return () => {
    queries.forEach((query) => query.removeEventListener("change", onChange));
    window.removeEventListener(CHOICE_EVENT, onChange);
  };
}

/**
 * Motion follows the system's reduced-motion setting until the presenter chooses, and the choice is
 * remembered. Pinned scenes need a tall, wide screen, so small screens get the plain flow layout.
 */
function useDisplay() {
  const value = useSyncExternalStore(
    subscribe,
    () => {
      const choice = storedChoice();
      const calm = choice ? choice === "reduced" : window.matchMedia(CALM).matches;
      const flow = calm || window.matchMedia(SMALL).matches;
      return `${calm ? "reduced" : "full"}:${flow ? "flow" : "stage"}`;
    },
    () => "full:stage",
  );
  const [motion, layout] = value.split(":");
  return { motion, layout };
}

function setChoice(choice: "full" | "reduced") {
  try {
    window.localStorage.setItem(CHOICE_KEY, choice);
  } catch {
    // Private windows may refuse storage; the choice then lasts until the page reloads.
  }
  window.dispatchEvent(new Event(CHOICE_EVENT));
}

/** The opening count, up to the Delhi to Goa distance shown on the home page. */
function Loader({ done, count }: { done: boolean; count: number }) {
  return (
    <div className="ab-loader" data-done={done || undefined} aria-hidden>
      <p className="ab-display">Assembling the journey</p>
      <p className="ab-loader__count">{count.toLocaleString("en-IN")} km</p>
    </div>
  );
}

/** A ring that trails the pointer, names what a click does, and floats a painting over `data-art` rows. */
function Cursor({ rootRef }: { rootRef: React.RefObject<HTMLDivElement | null> }) {
  const ring = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLSpanElement>(null);
  const float = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !window.matchMedia("(pointer: fine)").matches) return;
    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let shownX = x;
    let shownY = y;
    let frame = 0;
    const loop = () => {
      shownX += (x - shownX) * 0.18;
      shownY += (y - shownY) * 0.18;
      if (ring.current) ring.current.style.transform = `translate3d(${shownX}px, ${shownY}px, 0)`;
      if (float.current) float.current.style.transform = `translate3d(${shownX + 28}px, ${shownY - 110}px, 0) rotate(${(x - shownX) * 0.03}deg)`;
      root.style.setProperty("--mx", ((shownX / window.innerWidth - 0.5) * 2).toFixed(3));
      root.style.setProperty("--my", ((shownY / window.innerHeight - 0.5) * 2).toFixed(3));
      frame = requestAnimationFrame(loop);
    };
    const move = (event: PointerEvent) => {
      x = event.clientX;
      y = event.clientY;
      const target = event.target instanceof Element ? event.target : null;
      const named = target?.closest<HTMLElement>("[data-cursor], a, button");
      if (ring.current) {
        ring.current.dataset.shown = "true";
        ring.current.toggleAttribute("data-over", Boolean(named));
      }
      if (label.current) label.current.textContent = named?.dataset.cursor ?? "";
      const art = target?.closest<HTMLElement>("[data-art]")?.dataset.art;
      if (float.current) {
        if (art) float.current.style.backgroundImage = `url(${art})`;
        float.current.toggleAttribute("data-shown", Boolean(art));
      }
    };
    window.addEventListener("pointermove", move, { passive: true });
    frame = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(frame);
    };
  }, [rootRef]);

  return (
    <>
      <div ref={float} className="ab-float" aria-hidden />
      <div ref={ring} className="ab-ring" aria-hidden>
        <span ref={label} />
      </div>
    </>
  );
}

function isTyping(target: EventTarget | null) {
  return target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
}

/**
 * The About page, built as a presentation. Each scene is a full section of one long page: pinned
 * scenes animate from a scroll position, and the keyboard steps through them like slides.
 *
 * Keys: arrows, Space, PageUp and PageDown move; Home and End jump; F toggles full screen; M opens
 * the slide list. The URL hash follows the current scene, so any scene can be linked or reopened.
 */
export function Presentation({ fonts }: { fonts: string }) {
  const { motion, layout } = useDisplay();
  const root = useRef<HTMLDivElement>(null);
  const menu = useRef<HTMLDialogElement>(null);
  const lenis = useRef<Lenis | null>(null);
  const heading = useRef<{ top: number; until: number } | null>(null);
  const [ready, setReady] = useState(false);
  const [count, setCount] = useState(0);
  const [current, setCurrent] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const total = about.scenes.length;

  const scrollTo = useCallback((top: number, immediate = false) => {
    heading.current = immediate ? null : { top, until: performance.now() + GLIDE_SECONDS * 1000 };
    if (lenis.current) lenis.current.scrollTo(top, immediate ? { immediate: true, force: true } : { duration: GLIDE_SECONDS, force: true });
    else window.scrollTo({ top, behavior: "instant" });
  }, []);

  const openScene = useCallback(
    (id: string, immediate = false) => {
      const element = document.getElementById(id);
      if (element) scrollTo(element.getBoundingClientRect().top + window.scrollY, immediate);
    },
    [scrollTo],
  );

  /** Every place the keyboard stops. A pinned scene with `data-stops` gets several. */
  const stops = useCallback(() => {
    const list: number[] = [];
    root.current?.querySelectorAll<HTMLElement>("[data-scene]").forEach((element) => {
      const top = element.getBoundingClientRect().top + window.scrollY;
      const steps = Number(element.dataset.stops ?? 1);
      const length = element.offsetHeight - window.innerHeight;
      list.push(top);
      if (root.current?.dataset.layout === "stage" && length > 0) {
        for (let step = 1; step < steps; step++) list.push(top + (length * step) / (steps - 1));
      }
    });
    return list;
  }, []);

  const step = useCallback(
    (direction: 1 | -1) => {
      // Measure from where the scroll is heading, so a quick second press is not lost mid-glide.
      const glide = heading.current;
      const y = glide && performance.now() < glide.until ? glide.top : window.scrollY;
      const list = stops();
      const target = direction === 1 ? list.find((stop) => stop > y + 4) : list.filter((stop) => stop < y - 4).at(-1);
      if (target !== undefined) scrollTo(target);
    },
    [scrollTo, stops],
  );

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.();
  }, []);

  const openMenu = useCallback(() => {
    lenis.current?.stop();
    menu.current?.showModal();
  }, []);

  // Smooth scrolling, only while motion is on.
  useEffect(() => {
    if (motion !== "full") return;
    const instance = new Lenis({ autoRaf: true, lerp: 0.1, allowNestedScroll: true });
    lenis.current = instance;
    return () => {
      instance.destroy();
      lenis.current = null;
    };
  }, [motion]);

  // The opening: count up, then the cloud sharpens. Skipped when returning, deep-linking or calm.
  useEffect(() => {
    let seen = false;
    try {
      seen = window.sessionStorage.getItem(SEEN_KEY) === "1";
      window.sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      // Storage may be refused; the opening then simply plays again.
    }
    const hash = window.location.hash.slice(1);
    const skip = motion !== "full" || seen || Boolean(hash);
    const start = performance.now();
    const duration = 1900;
    let frame = requestAnimationFrame(function tick(now) {
      const progress = skip ? 1 : Math.min(1, (now - start) / duration);
      setCount(Math.round((1 - Math.pow(1 - progress, 3)) * 1503));
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
        return;
      }
      setReady(true);
      if (hash) openScene(hash, true);
    });
    return () => cancelAnimationFrame(frame);
  }, [motion, openScene]);

  // Follow the scene crossing the middle of the screen, and mirror it into the URL.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const index = about.scenes.findIndex((scene) => scene.id === entry.target.id);
          if (index < 0) continue;
          setCurrent(index);
          window.history.replaceState(window.history.state, "", index === 0 ? window.location.pathname : `#${entry.target.id}`);
        }
      },
      { rootMargin: "-50% 0px -50% 0px" },
    );
    root.current?.querySelectorAll("[data-scene]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  // Scroll position for the progress line and the background geometry.
  useEffect(() => {
    let queued = false;
    const measure = () => {
      queued = false;
      const height = document.documentElement.scrollHeight - window.innerHeight;
      root.current?.style.setProperty("--page", (height > 0 ? window.scrollY / height : 0).toFixed(4));
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

  // Fade rows and panels in once, as they first come into view.
  useEffect(() => {
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
    root.current?.querySelectorAll("[data-reveal]").forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (menu.current?.open || isTyping(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      const onControl = event.target instanceof HTMLElement && /^(BUTTON|A)$/.test(event.target.tagName);
      if (event.key === " " && onControl) return;
      if (["ArrowDown", "ArrowRight", "PageDown", " "].includes(event.key)) step(1);
      else if (["ArrowUp", "ArrowLeft", "PageUp"].includes(event.key)) step(-1);
      else if (event.key === "Home") scrollTo(0);
      else if (event.key === "End") scrollTo(document.documentElement.scrollHeight);
      else if (event.key.toLowerCase() === "f") toggleFullscreen();
      else if (event.key.toLowerCase() === "m") openMenu();
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
  }, [openMenu, scrollTo, step, toggleFullscreen]);

  return (
    <div ref={root} className={`ab ${fonts}`} data-motion={motion} data-layout={layout} data-ready={ready || undefined}>
      <Loader done={ready} count={count} />
      <Cursor rootRef={root} />

      <svg className="ab-lines" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" aria-hidden>
        <circle cx="500" cy="500" r="330" />
        <circle cx="500" cy="500" r="470" />
        <circle cx="500" cy="170" r="330" />
        <circle cx="500" cy="830" r="330" />
        <path d="M0 500H1000M500 0V1000M146 146L854 854M854 146L146 854" />
      </svg>

      <header className="ab-head">
        <Link href="/" data-cursor="Home">
          ← {about.titleMeaning.name}
        </Link>
      </header>

      <Scenes />

      <div className="ab-dock">
        <div className="ab-dock__left">
          <span className="ab-dock__count" aria-live="polite">
            {String(current + 1).padStart(2, "0")} / {total}
          </span>
          <span className="ab-dock__wide">
            <button type="button" aria-label="Previous slide" onClick={() => step(-1)}>
              <ChevronUp aria-hidden />
            </button>
            <button type="button" aria-label="Next slide" onClick={() => step(1)}>
              <ChevronDown aria-hidden />
            </button>
            <button type="button" onClick={toggleFullscreen}>
              {fullscreen ? <Minimize2 aria-hidden /> : <Maximize2 aria-hidden />}
              {fullscreen ? "Exit" : "Present"}
            </button>
          </span>
          <button
            type="button"
            className="ab-dock__motion"
            data-off={motion !== "full" || undefined}
            onClick={() => setChoice(motion === "full" ? "reduced" : "full")}
          >
            {motion === "full" ? "Motion on" : "Motion off · turn on"}
          </button>
        </div>
        <button type="button" className="ab-dock__menu" aria-label="All slides" data-cursor="Slides" onClick={openMenu}>
          <MenuIcon aria-hidden />
        </button>
      </div>
      <div className="ab-progress" aria-hidden />

      <dialog
        ref={menu}
        className={`ab-menu ${fonts}`}
        aria-label="All slides"
        onClose={() => lenis.current?.start()}
        onClick={(event) => {
          if (event.target === menu.current) menu.current?.close();
        }}
      >
        <nav aria-label="Slides">
          <ol>
            {about.scenes.map((scene, index) => (
              <li key={scene.id}>
                <a
                  href={`#${scene.id}`}
                  aria-current={index === current ? "true" : undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    menu.current?.close();
                    // Restart scrolling first: the close event would otherwise restart it later and cancel the jump.
                    lenis.current?.start();
                    openScene(scene.id);
                  }}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  {scene.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <button type="button" className="ab-menu__close" aria-label="Close" onClick={() => menu.current?.close()}>
          <X aria-hidden />
        </button>
      </dialog>
    </div>
  );
}
