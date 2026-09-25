"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { QRCodeSVG } from "qrcode.react";
import { Link2, PhoneOutgoing, Rocket } from "lucide-react";
import { toast } from "sonner";
import { CopyButton, EmptyState, Field, UpgradeCallout, notifyError } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useSurvey } from "@/lib/use-survey";
import { timeAgo } from "@/lib/utils";
import type { Outreach, Page } from "@/lib/types";

const OUTREACH_TONE = { queued: "neutral", calling: "info", completed: "success", failed: "danger" } as const;

function parseContacts(text: string) {
  const contacts: { name: string; phone: string }[] = [];
  const invalid: string[] = [];
  for (const line of text.split("\n").map((l) => l.trim()).filter(Boolean)) {
    const match = line.match(/(\+[1-9][\d\s().-]{7,20})/);
    if (!match) {
      invalid.push(line);
      continue;
    }
    const phone = "+" + match[1].replace(/\D/g, "");
    const name = line.replace(match[1], "").replace(/[,;\t]/g, " ").trim();
    contacts.push({ name, phone });
  }
  return { contacts, invalid };
}

function PhoneOutreach({ surveyId }: { surveyId: string }) {
  const { org, can } = useSession();
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const { data, mutate } = useSWR<Page<Outreach>>(`/surveys/${surveyId}/outreach?per_page=50`, {
    refreshInterval: (latest) => (latest?.items.some((o) => o.status === "queued" || o.status === "calling") ? 5000 : 0),
  });
  const hasPhone = org?.plan === "team" || org?.plan === "enterprise";
  const { contacts, invalid } = parseContacts(text);

  async function send() {
    setSending(true);
    try {
      await api(`/surveys/${surveyId}/outreach`, { method: "POST", body: { contacts } });
      toast.success(`Calling ${contacts.length} contact${contacts.length === 1 ? "" : "s"}`);
      setText("");
      mutate();
    } catch (err) {
      notifyError(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="glass-panel rounded-2xl p-6">
      <div className="flex items-center gap-3">
        <PhoneOutgoing className="h-5 w-5 text-cyan-400" />
        <h2 className="font-display text-lg font-semibold">Phone interviews</h2>
      </div>
      <p className="mt-1.5 text-sm text-ink-muted">
        The voice agent calls each contact, runs the interview conversationally, and files structured answers when the call ends.
      </p>
      {!hasPhone ? (
        <UpgradeCallout feature="Outbound phone interviews" plan="Team" className="mt-5" />
      ) : (
        <>
          {can("editor") && (
            <div className="mt-5 space-y-3">
              <Field label="Contacts" htmlFor="contacts" hint="One per line: name and phone in international format, e.g. “Ana Lopez, +14035550100”.">
                <Textarea id="contacts" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder={"Ana Lopez, +14035550100\n+442071838750"} />
              </Field>
              {invalid.length > 0 && <p className="text-xs text-amber-300">Skipping {invalid.length} line(s) without a +country phone number.</p>}
              <div className="flex justify-end">
                <Button onClick={send} disabled={!contacts.length} loading={sending}>
                  Call {contacts.length || ""} {contacts.length === 1 ? "contact" : "contacts"}
                </Button>
              </div>
            </div>
          )}
          <div className="mt-6">
            {!data ? (
              <Skeleton className="h-24" />
            ) : data.items.length === 0 ? (
              <p className="text-sm text-ink-faint">No calls placed yet.</p>
            ) : (
              <div className="overflow-hidden rounded-xl border border-white/[0.08]">
                <table className="w-full text-sm">
                  <thead className="bg-white/[0.03] text-left text-xs uppercase tracking-wider text-ink-faint">
                    <tr>
                      <th className="px-4 py-2.5 font-medium">Contact</th>
                      <th className="px-4 py-2.5 font-medium">Status</th>
                      <th className="px-4 py-2.5 text-right font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.06]">
                    {data.items.map((o) => (
                      <tr key={o.id}>
                        <td className="px-4 py-3">
                          <div className="text-ink">{o.name || "Unnamed"}</div>
                          <div className="font-mono text-xs text-ink-faint">{o.phone}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge tone={OUTREACH_TONE[o.status]} className="capitalize">
                            {o.status}
                          </Badge>
                          {o.error && <div className="mt-1 text-xs text-red-300">{o.error}</div>}
                        </td>
                        <td className="px-4 py-3 text-right text-xs text-ink-faint">{timeAgo(o.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export default function SharePage() {
  const { id, survey } = useSurvey();
  const [origin, setOrigin] = useState("");
  useEffect(() => setOrigin(window.location.origin), []);

  if (!survey) return <Skeleton className="h-96 rounded-xl" />;
  if (survey.status === "draft") {
    return (
      <EmptyState
        icon={<Rocket />}
        title="Publish to start sharing"
        description="Your survey is a draft. Publish it from the top of the page to get a shareable link."
      />
    );
  }

  const url = `${origin}/s/${survey.public_token}`;
  const embed = `<iframe src="${url}?embed=1" width="100%" height="680" style="border:0;border-radius:16px" allow="microphone" title="${survey.title.replace(/"/g, "&quot;")}"></iframe>`;

  return (
    <div className="space-y-6">
      {survey.status === "closed" && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-4 text-sm text-amber-200">
          This survey is closed, so the link shows a “no longer accepting responses” message. Reopen it to collect more.
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_240px]">
        <section className="glass-panel rounded-2xl p-6">
          <div className="flex items-center gap-3">
            <Link2 className="h-5 w-5 text-cyan-400" />
            <h2 className="font-display text-lg font-semibold">Survey link</h2>
          </div>
          <div className="mt-4 flex gap-2">
            <Input value={url} readOnly className="font-mono text-xs" onFocus={(e) => e.target.select()} />
            <CopyButton value={url} />
          </div>
          <div className="mt-5 space-y-2">
            <div className="text-xs font-medium uppercase tracking-wider text-ink-faint">Direct links by mode</div>
            {survey.settings.modes.map((mode) => (
              <div key={mode} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2">
                <span className="text-sm capitalize text-ink-muted">{mode}</span>
                <CopyButton value={`${url}?mode=${mode}`} label="Copy link" />
              </div>
            ))}
          </div>
          <div className="mt-6">
            <div className="mb-2 text-xs font-medium uppercase tracking-wider text-ink-faint">Embed on your site</div>
            <Textarea value={embed} readOnly rows={3} className="font-mono text-xs" onFocus={(e) => e.target.select()} />
            <div className="mt-2 flex justify-end">
              <CopyButton value={embed} label="Copy embed code" />
            </div>
          </div>
        </section>
        <section className="glass-panel flex flex-col items-center rounded-2xl p-6">
          <div className="rounded-xl bg-white p-3">
            <QRCodeSVG value={url || "https://"} size={168} />
          </div>
          <p className="mt-3 text-center text-xs text-ink-muted">Scan to open. Great for printed material and events.</p>
        </section>
      </div>
      <PhoneOutreach surveyId={id} />
    </div>
  );
}
