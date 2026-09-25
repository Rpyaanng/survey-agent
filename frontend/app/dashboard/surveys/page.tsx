"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { ListChecks, Plus, Search } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/shared";
import { SurveyRow } from "@/components/survey-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { Page, Survey } from "@/lib/types";

const FILTERS = [
  { value: "", label: "All" },
  { value: "published", label: "Live" },
  { value: "draft", label: "Drafts" },
  { value: "closed", label: "Closed" },
];

export default function SurveysPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), per_page: "20" });
  if (status) params.set("status", status);
  if (query.trim()) params.set("q", query.trim());
  const { data } = useSWR<Page<Survey>>(`/surveys?${params}`, { keepPreviousData: true });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <>
      <PageHeader
        title="Surveys"
        description="Build, launch and analyze every survey in your workspace."
        actions={
          can("editor") && (
            <Button asChild>
              <Link href="/dashboard/surveys/new">
                <Plus /> New survey
              </Link>
            </Button>
          )
        }
      />

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] p-1">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => {
                setStatus(f.value);
                setPage(1);
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                status === f.value ? "bg-white/10 text-ink" : "text-ink-muted hover:text-ink",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search surveys"
            className="pl-9"
            aria-label="Search surveys"
          />
        </div>
      </div>

      {!data ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[72px] rounded-xl" />
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <EmptyState
          icon={<ListChecks />}
          title={query || status ? "No surveys match" : "No surveys yet"}
          description={query || status ? "Try a different search or filter." : "Create a survey to start collecting responses."}
        />
      ) : (
        <>
          <div className="space-y-3">
            {data.items.map((s) => (
              <SurveyRow key={s.id} survey={s} />
            ))}
          </div>
          {pages > 1 && (
            <div className="mt-6 flex items-center justify-between text-sm text-ink-muted">
              <span>
                Page {page} of {pages}
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
