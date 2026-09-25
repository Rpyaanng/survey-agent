import type { ReactNode } from "react";
import { MarketingBackdrop, MarketingFooter, MarketingNav } from "@/components/marketing/site-chrome";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <MarketingBackdrop />
      <MarketingNav />
      <main>{children}</main>
      <MarketingFooter />
    </>
  );
}
