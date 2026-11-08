import fs from "node:fs";
import path from "node:path";

import { Cormorant_Garamond, Inter_Tight, Oswald } from "next/font/google";

import { homeMedia, type MediaSlot } from "@/content/home";
import { HomeExperience } from "@/features/home/home-experience";
import type { MediaFiles } from "@/features/home/media";

const display = Oswald({ subsets: ["latin"], variable: "--tm-display" });
const serif = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--tm-serif",
  weight: ["400", "500"],
  style: ["normal", "italic"],
});
const sans = Inter_Tight({ subsets: ["latin"], variable: "--tm-sans" });

const IMAGE = /\.(jpe?g|png|webp|avif)$/i;
const VIDEO = /\.(mp4|webm)$/i;

/** Which media files have been added to public/home. A missing file stays a placeholder. */
function findMedia(): MediaFiles {
  let names: string[] = [];
  try {
    names = fs.readdirSync(path.join(process.cwd(), "public", "home"));
  } catch {
    return {};
  }
  const url = (name: string) => `/home/${encodeURIComponent(name)}`;
  const baseOf = (name: string) => name.slice(0, name.lastIndexOf("."));
  const found: MediaFiles = {};
  for (const slot of Object.keys(homeMedia) as MediaSlot[]) {
    const image = names.find((name) => baseOf(name) === slot && IMAGE.test(name));
    const video = names.find((name) => baseOf(name) === slot && VIDEO.test(name));
    if (homeMedia[slot].kind === "video" && video) {
      found[slot] = { src: url(video), poster: image ? url(image) : undefined };
    } else if (homeMedia[slot].kind === "image" && image) {
      found[slot] = { src: url(image) };
    }
  }
  return found;
}

export default function HomePage() {
  return <HomeExperience media={findMedia()} fonts={`${display.variable} ${serif.variable} ${sans.variable}`} />;
}
