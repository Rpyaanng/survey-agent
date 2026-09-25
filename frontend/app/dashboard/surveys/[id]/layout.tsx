"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ArrowLeft, Copy, ExternalLink, MoreHorizontal, Rocket, Square, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { SurveyStatusBadge, notifyError } from "@/components/shared";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useSurvey } from "@/lib/use-survey";
import { cn } from "@/lib/utils";
import type { Survey } from "@/lib/types";

const TABS = [
  { href: "", label: "Build" },
  { href: "/settings", label: "Settings" },
  { href: "/share", label: "Share" },
  { href: "/responses", label: "Responses" },
  { href: "/analytics", label: "Analytics" },
];

export default function SurveyLayout({ children }: { children: ReactNode }) {
  const { id, survey, mutate } = useSurvey();
  const { can } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const base = `/dashboard/surveys/${id}`;

  async function action(path: string, success: string) {
    setBusy(true);
    try {
      const updated = await api<Survey>(`/surveys/${id}/${path}`, { method: "POST" });
      await mutate(updated, { revalidate: false });
      toast.success(success);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  }

  async function duplicate() {
    try {
      const copy = await api<Survey>(`/surveys/${id}/duplicate`, { method: "POST" });
      toast.success("Survey duplicated");
      router.push(`/dashboard/surveys/${copy.id}`);
    } catch (err) {
      notifyError(err);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this survey and all of its responses? This can't be undone.")) return;
    try {
      await api(`/surveys/${id}`, { method: "DELETE" });
      toast.success("Survey deleted");
      router.replace("/dashboard/surveys");
    } catch (err) {
      notifyError(err);
    }
  }

  return (
    <>
      <Link href="/dashboard/surveys" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> All surveys
      </Link>
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        {survey ? (
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <h1 className="truncate font-display text-2xl font-bold tracking-tight sm:text-3xl">{survey.title}</h1>
              <SurveyStatusBadge status={survey.status} />
            </div>
            <p className="mt-1 text-sm text-ink-faint">
              {survey.question_count} questions · {survey.responses?.completed ?? 0} completed responses
            </p>
          </div>
        ) : (
          <Skeleton className="h-12 w-80" />
        )}
        {survey && (
          <div className="flex items-center gap-2">
            {survey.status !== "draft" && (
              <Button asChild variant="secondary">
                <a href={`/s/${survey.public_token}`} target="_blank" rel="noreferrer">
                  <ExternalLink /> Open
                </a>
              </Button>
            )}
            {can("editor") &&
              (survey.status === "published" ? (
                <Button variant="secondary" loading={busy} onClick={() => action("close", "Survey closed")}>
                  <Square /> Close
                </Button>
              ) : (
                <Button loading={busy} onClick={() => action("publish", "Survey is live")}>
                  <Rocket /> {survey.status === "closed" ? "Reopen" : "Publish"}
                </Button>
              ))}
            {can("editor") && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="More actions">
                    <MoreHorizontal />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="border-white/10 bg-popover">
                  <DropdownMenuItem onClick={duplicate} className="gap-2">
                    <Copy className="h-4 w-4" /> Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={remove} className="gap-2 text-red-300">
                    <Trash2 className="h-4 w-4" /> Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        )}
      </div>

      <nav className="mb-8 flex gap-1 overflow-x-auto border-b border-white/[0.08]">
        {TABS.map((tab) => {
          const href = base + tab.href;
          const active = tab.href === "" ? pathname === base : pathname.startsWith(href);
          return (
            <Link
              key={tab.label}
              href={href}
              className={cn(
                "-mb-px border-b-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors",
                active ? "border-cyan-400 text-ink" : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </>
  );
}
