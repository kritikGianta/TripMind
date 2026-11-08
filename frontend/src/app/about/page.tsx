import type { Metadata } from "next";
import { Bodoni_Moda, Inter_Tight } from "next/font/google";

import { Presentation } from "@/features/about/presentation";

export const metadata: Metadata = {
  title: "About",
  description: "Why TripMind exists, how it works, and what is built today.",
};

const display = Bodoni_Moda({ subsets: ["latin"], style: ["normal", "italic"], variable: "--ab-display" });
const sans = Inter_Tight({ subsets: ["latin"], variable: "--ab-sans" });

export default function AboutPage() {
  return <Presentation fonts={`${display.variable} ${sans.variable}`} />;
}
