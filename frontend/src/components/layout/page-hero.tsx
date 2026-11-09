import Image from "next/image";
import type { ReactNode } from "react";

/** The photo banner at the top of inner pages. `overlap` leaves room for a panel laid over its edge. */
export function PageHero({
  title,
  eyebrow,
  text,
  image,
  position,
  compact,
  overlap,
  as: Title = "h1",
  children,
}: {
  title: string;
  eyebrow?: string;
  text?: string;
  image: string;
  position?: string;
  compact?: boolean;
  overlap?: boolean;
  /** Use "p" where the page already has its own main heading. */
  as?: "h1" | "p";
  children?: ReactNode;
}) {
  return (
    <section className="tm-page-hero" data-compact={compact || undefined} data-overlap={overlap || undefined}>
      <Image src={image} alt="" fill sizes="100vw" priority style={position ? { objectPosition: position } : undefined} />
      <div className="tm-page-hero__inner">
        {eyebrow ? <p className="tm-page-hero__eyebrow">{eyebrow}</p> : null}
        <Title className="tm-page-hero__title">{title}</Title>
        {text ? <p className="tm-page-hero__text">{text}</p> : null}
        {children}
      </div>
    </section>
  );
}
