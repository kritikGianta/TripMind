"use client";

import Lenis from "lenis";
import { useEffect, useRef } from "react";

/**
 * The home page's scroll engine. Sections are sticky in CSS and animate from one custom property,
 * `--p` (0 to 1), written here once per frame. No layout is touched, so scrolling stays smooth and
 * the page works without JavaScript or with reduced motion.
 *
 * - "pin": 0 when the section's top reaches the viewport top, 1 when its bottom reaches the bottom.
 * - "pass": 0 when the section enters from below, 1 when it has left at the top.
 */
type Mode = "pin" | "pass";
type Item = { el: HTMLElement; mode: Mode; last: number; onFrame?: (p: number, el: HTMLElement) => void };

const items = new Set<Item>();
let queued = false;

function measure() {
  queued = false;
  const vh = window.innerHeight;
  items.forEach((item) => {
    const rect = item.el.getBoundingClientRect();
    const raw = item.mode === "pin" ? -rect.top / Math.max(1, rect.height - vh) : (vh - rect.top) / (vh + rect.height);
    const p = Math.min(1, Math.max(0, raw));
    if (Math.abs(p - item.last) < 0.0005) return;
    item.last = p;
    item.el.style.setProperty("--p", p.toFixed(4));
    item.onFrame?.(p, item.el);
  });
}

function schedule() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(measure);
}

export function useScrollProgress<T extends HTMLElement>(mode: Mode, onFrame?: (p: number, el: HTMLElement) => void) {
  const ref = useRef<T>(null);
  const callback = useRef(onFrame);
  useEffect(() => {
    callback.current = onFrame;
  });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const item: Item = { el, mode, last: -1, onFrame: (p, target) => callback.current?.(p, target) };
    if (items.size === 0) {
      window.addEventListener("scroll", schedule, { passive: true });
      window.addEventListener("resize", schedule);
    }
    items.add(item);
    schedule();
    return () => {
      items.delete(item);
      if (items.size === 0) {
        window.removeEventListener("scroll", schedule);
        window.removeEventListener("resize", schedule);
      }
    };
  }, [mode]);
  return ref;
}

let lenis: Lenis | null = null;

/** Scroll to a section on this page, through the smooth scroller when it is running. */
export function scrollToSection(selector: string) {
  const target = document.querySelector<HTMLElement>(selector);
  if (!target) return;
  if (lenis) lenis.scrollTo(target, { offset: -40 });
  else target.scrollIntoView();
}

/** Anything that scrolls on its own: dialogs, dropdowns, the assistant. */
const OWN_SCROLL = '[role="dialog"], [role="listbox"], [data-slot$="overlay"], [data-radix-popper-content-wrapper]';

/** Smooth wheel scrolling for the home page only; other pages keep native scrolling. */
export function SmoothScroll({ enabled }: { enabled: boolean }) {
  useEffect(() => {
    if (!enabled) return;
    const instance = new Lenis({
      autoRaf: true,
      lerp: 0.11,
      allowNestedScroll: true,
      prevent: (node) => node.matches(OWN_SCROLL),
    });
    lenis = instance;
    return () => {
      instance.destroy();
      lenis = null;
    };
  }, [enabled]);
  return null;
}

/**
 * A tiny dot that trails the mouse and names what a click will do, from `data-cursor`.
 * It also feeds the pointer's position to the page as --mx and --my, and pulls glass chips gently
 * towards the pointer while it is over them.
 */
export function CursorDot({ enabled }: { enabled: boolean }) {
  const dot = useRef<HTMLDivElement>(null);
  const label = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = dot.current;
    const text = label.current;
    if (!el || !text || !enabled || !window.matchMedia("(pointer: fine)").matches) return;
    // Only the hero reads the pointer. Writing to a page-wide element would restyle the whole page.
    const hero = document.querySelector<HTMLElement>(".tm-hero");

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let shownX = x;
    let shownY = y;
    let frame = 0;
    let pulled: HTMLElement | null = null;
    const release = () => {
      if (pulled) pulled.style.transform = "";
      pulled = null;
    };
    const loop = () => {
      frame = requestAnimationFrame(loop);
      if (Math.abs(x - shownX) < 0.2 && Math.abs(y - shownY) < 0.2) return;
      shownX += (x - shownX) * 0.22;
      shownY += (y - shownY) * 0.22;
      el.style.transform = `translate3d(${shownX}px, ${shownY}px, 0)`;
      if (hero && window.scrollY < window.innerHeight) {
        hero.style.setProperty("--mx", ((shownX / window.innerWidth - 0.5) * 2).toFixed(3));
        hero.style.setProperty("--my", ((shownY / window.innerHeight - 0.5) * 2).toFixed(3));
      }
    };
    const move = (event: PointerEvent) => {
      x = event.clientX;
      y = event.clientY;
      el.style.opacity = "1";
      const target = event.target instanceof Element ? event.target : null;
      text.textContent = target?.closest<HTMLElement>("[data-cursor]")?.dataset.cursor ?? "";
      const chip = target?.closest<HTMLElement>(".tm-chip") ?? null;
      if (chip !== pulled) release();
      if (chip) {
        pulled = chip;
        const box = chip.getBoundingClientRect();
        chip.style.transform = `translate(${(x - box.left - box.width / 2) * 0.16}px, ${(y - box.top - box.height / 2) * 0.26}px)`;
      }
    };
    window.addEventListener("pointermove", move, { passive: true });
    frame = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener("pointermove", move);
      cancelAnimationFrame(frame);
      release();
      el.style.opacity = "";
      hero?.style.removeProperty("--mx");
      hero?.style.removeProperty("--my");
    };
  }, [enabled]);

  return (
    <div ref={dot} className="tm-cursor" aria-hidden>
      <i />
      <span ref={label} />
    </div>
  );
}
