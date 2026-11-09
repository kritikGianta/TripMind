"use client";

import { useSyncExternalStore } from "react";

// The name dates from when only the About page had this switch; kept so existing choices still apply.
const CHOICE_KEY = "tm-about-motion";
const CHOICE_EVENT = "tm-motion-choice";
const CALM = "(prefers-reduced-motion: reduce)";

function storedChoice() {
  try {
    return window.localStorage.getItem(CHOICE_KEY);
  } catch {
    return null;
  }
}

function subscribeToChoice(onChange: () => void) {
  const query = window.matchMedia(CALM);
  query.addEventListener("change", onChange);
  window.addEventListener(CHOICE_EVENT, onChange);
  return () => {
    query.removeEventListener("change", onChange);
    window.removeEventListener(CHOICE_EVENT, onChange);
  };
}

/**
 * Whether the animated pages run in full. Follows the system's reduced-motion setting until the
 * visitor chooses with the Motion button; that choice is remembered and shared across pages.
 */
export function useMotionChoice(): "full" | "reduced" {
  return useSyncExternalStore(
    subscribeToChoice,
    () => {
      const choice = storedChoice();
      const calm = choice ? choice === "reduced" : window.matchMedia(CALM).matches;
      return calm ? "reduced" : "full";
    },
    () => "full",
  );
}

export function setMotionChoice(choice: "full" | "reduced") {
  try {
    window.localStorage.setItem(CHOICE_KEY, choice);
  } catch {
    // Private windows may refuse storage; the choice then lasts until the page reloads.
  }
  window.dispatchEvent(new Event(CHOICE_EVENT));
}

export function useMediaQuery(query: string) {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
