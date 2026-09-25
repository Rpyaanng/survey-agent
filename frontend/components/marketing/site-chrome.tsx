"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function MarketingNav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled ? "border-b border-white/[0.06] bg-ground/80 backdrop-blur-xl" : "bg-transparent",
      )}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm text-ink-muted md:flex">
          <a href="/#channels" className="hover:text-ink">Channels</a>
          <a href="/#how" className="hover:text-ink">How it works</a>
          <a href="/#features" className="hover:text-ink">Features</a>
          <Link href="/pricing" className="hover:text-ink">Pricing</Link>
        </nav>
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/signup">Start free</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-white/[0.06]">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div>
          <Logo />
          <p className="mt-2 text-sm text-ink-faint">Conversational surveys, structured results.</p>
        </div>
        <div className="flex gap-6 text-sm text-ink-muted">
          <Link href="/pricing" className="hover:text-ink">Pricing</Link>
          <Link href="/login" className="hover:text-ink">Sign in</Link>
          <a href="mailto:hello@surveyagent.dev" className="hover:text-ink">Contact</a>
        </div>
        <p className="text-xs text-ink-faint">© {new Date().getFullYear()} Survey Agent</p>
      </div>
    </footer>
  );
}

export function MarketingBackdrop() {
  return (
    <>
      <div className="grain pointer-events-none fixed inset-0 z-40" aria-hidden />
    </>
  );
}
