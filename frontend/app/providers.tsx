"use client";

import type { ReactNode } from "react";
import { SWRConfig } from "swr";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { fetcher } from "@/lib/api";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false }}>
      <TooltipProvider delayDuration={200}>
        {children}
        <Toaster theme="dark" richColors position="bottom-right" />
      </TooltipProvider>
    </SWRConfig>
  );
}
