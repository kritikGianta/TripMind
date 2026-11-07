import type { Metadata } from "next";

import { Deck } from "@/features/about/deck";
import { buildSlides } from "@/features/about/slides";

export const metadata: Metadata = {
  title: "About",
  description: "Why TripMind exists, how it works, and what is built today.",
};

export default function AboutPage() {
  return <Deck slides={buildSlides()} />;
}
