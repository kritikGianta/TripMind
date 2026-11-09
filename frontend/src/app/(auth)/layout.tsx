import Image from "next/image";
import type { ReactNode } from "react";

import { siteConfig } from "@/config/site";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="tm-auth">
      <div className="tm-auth__art">
        <Image src="/home/cta-landscape.png" alt="" fill sizes="55vw" priority />
        <p className="tm-auth__quote">{siteConfig.tagline}</p>
      </div>
      <div className="tm-auth__form">
        <div>{children}</div>
      </div>
    </div>
  );
}
