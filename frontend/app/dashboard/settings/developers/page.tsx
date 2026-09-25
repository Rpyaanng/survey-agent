"use client";

import { useState } from "react";
import useSWR from "swr";
import { KeyRound, Send, Trash2, Webhook as WebhookIcon } from "lucide-react";
import { toast } from "sonner";
import { CopyButton, EmptyState, PageHeader, UpgradeCallout, notifyError } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { timeAgo } from "@/lib/utils";
import type { ApiKey, Webhook } from "@/lib/types";

const EVENTS = [
  { id: "response.completed", label: "Response completed" },
  { id: "survey.published", label: "Survey published" },
  { id: "survey.closed", label: "Survey closed" },
];

function Secret({ label, value, onDismiss }: { label: string; value: string; onDismiss: () => void }) {
  return (
    <div className="rounded-xl border border-emerald-400/25 bg-emerald-400/[0.06] p-4">
      <p className="text-sm text-emerald-200">{label}</p>
      <div className="mt-3 flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg bg-black/30 px-3 py-2 font-mono text-xs text-ink">{value}</code>
        <CopyButton value={value} />
        <Button variant="ghost" size="sm" onClick={onDismiss}>
          Done
        </Button>
      </div>
    </div>
  );
}

function ApiKeys() {
  const { data, mutate } = useSWR<{ items: ApiKey[] }>("/api-keys");
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const key = await api<ApiKey>("/api-keys", { method: "POST", body: { name } });
      setCreated(key.key ?? null);
      setName("");
      mutate();
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(key: ApiKey) {
    if (!window.confirm(`Revoke “${key.name}”? Integrations using it will stop working immediately.`)) return;
    try {
      await api(`/api-keys/${key.id}`, { method: "DELETE" });
      mutate();
    } catch (err) {
      notifyError(err);
    }
  }

  return (
    <section className="glass-panel rounded-2xl p-6">
      <div className="flex items-center gap-3">
        <KeyRound className="h-5 w-5 text-cyan-400" />
        <h2 className="font-display text-lg font-semibold">API keys</h2>
      </div>
      <p className="mt-1.5 text-sm text-ink-muted">
        Authenticate REST calls with <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-xs">Authorization: Bearer sa_live_…</code>. Keys have
        editor access to this workspace.
      </p>
      <form onSubmit={create} className="mt-5 flex gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Key name, e.g. “Zapier” or “Data warehouse”" required aria-label="Key name" />
        <Button type="submit" loading={busy}>
          Create key
        </Button>
      </form>
      {created && <div className="mt-4"><Secret label="Copy this key now. You won't be able to see it again." value={created} onDismiss={() => setCreated(null)} /></div>}
      <div className="mt-5">
        {!data ? (
          <Skeleton className="h-16" />
        ) : data.items.length === 0 ? (
          <p className="text-sm text-ink-faint">No active keys.</p>
        ) : (
          <ul className="divide-y divide-white/[0.06] rounded-xl border border-white/[0.08]">
            {data.items.map((key) => (
              <li key={key.id} className="flex items-center gap-4 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-ink">{key.name}</div>
                  <div className="font-mono text-xs text-ink-faint">{key.prefix}…</div>
                </div>
                <div className="hidden text-right text-xs text-ink-faint sm:block">
                  <div>Created {timeAgo(key.created_at)}</div>
                  <div>{key.last_used_at ? `Last used ${timeAgo(key.last_used_at)}` : "Never used"}</div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => revoke(key)} aria-label="Revoke key" className="hover:text-red-300">
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function Webhooks() {
  const { data, mutate } = useSWR<{ items: Webhook[] }>("/webhooks");
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>(["response.completed"]);
  const [secret, setSecret] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!events.length) return toast.error("Pick at least one event");
    setBusy(true);
    try {
      const hook = await api<Webhook>("/webhooks", { method: "POST", body: { url, events } });
      setSecret(hook.secret ?? null);
      setUrl("");
      mutate();
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  }

  async function test(hook: Webhook) {
    try {
      const res = await api<{ delivered: boolean; status: number | null }>(`/webhooks/${hook.id}/test`, { method: "POST" });
      if (res.delivered) toast.success(`Delivered (HTTP ${res.status})`);
      else toast.error(res.status ? `Endpoint returned HTTP ${res.status}` : "Couldn't reach the endpoint");
      mutate();
    } catch (err) {
      notifyError(err);
    }
  }

  async function toggle(hook: Webhook, active: boolean) {
    await api(`/webhooks/${hook.id}`, { method: "PATCH", body: { active } }).catch(notifyError);
    mutate();
  }

  async function remove(hook: Webhook) {
    if (!window.confirm("Delete this webhook endpoint?")) return;
    await api(`/webhooks/${hook.id}`, { method: "DELETE" }).catch(notifyError);
    mutate();
  }

  return (
    <section className="glass-panel rounded-2xl p-6">
      <div className="flex items-center gap-3">
        <WebhookIcon className="h-5 w-5 text-cyan-400" />
        <h2 className="font-display text-lg font-semibold">Webhooks</h2>
      </div>
      <p className="mt-1.5 text-sm text-ink-muted">
        We POST signed JSON events to your endpoint. Verify the <code className="font-mono text-xs">X-SurveyAgent-Signature</code> header (
        <code className="font-mono text-xs">t=…,v1=HMAC-SHA256(secret, &quot;t.body&quot;)</code>).
      </p>
      <form onSubmit={create} className="mt-5 space-y-3">
        <div className="flex gap-2">
          <Input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/webhooks/survey-agent" required aria-label="Endpoint URL" />
          <Button type="submit" loading={busy}>
            Add endpoint
          </Button>
        </div>
        <div className="flex flex-wrap gap-4">
          {EVENTS.map((ev) => (
            <label key={ev.id} className="flex items-center gap-2 text-sm text-ink-muted">
              <input
                type="checkbox"
                checked={events.includes(ev.id)}
                onChange={(e) => setEvents(e.target.checked ? [...events, ev.id] : events.filter((x) => x !== ev.id))}
                className="accent-cyan-400"
              />
              {ev.label}
            </label>
          ))}
        </div>
      </form>
      {secret && <div className="mt-4"><Secret label="Signing secret. Store it with your endpoint to verify deliveries." value={secret} onDismiss={() => setSecret(null)} /></div>}
      <div className="mt-5">
        {!data ? (
          <Skeleton className="h-16" />
        ) : data.items.length === 0 ? (
          <p className="text-sm text-ink-faint">No endpoints yet.</p>
        ) : (
          <ul className="divide-y divide-white/[0.06] rounded-xl border border-white/[0.08]">
            {data.items.map((hook) => (
              <li key={hook.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-sm text-ink">{hook.url}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                    {hook.events.map((e) => (
                      <Badge key={e}>{e}</Badge>
                    ))}
                    {hook.last_status != null && (
                      <span className={hook.last_status < 300 ? "text-emerald-300" : "text-red-300"}>
                        Last delivery HTTP {hook.last_status} · {timeAgo(hook.last_delivery_at)}
                      </span>
                    )}
                    {hook.failure_count > 0 && <span className="text-amber-300">{hook.failure_count} consecutive failures</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={hook.active} onCheckedChange={(v) => toggle(hook, v)} aria-label="Active" />
                  <Button variant="ghost" size="sm" onClick={() => test(hook)}>
                    <Send /> Test
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => remove(hook)} aria-label="Delete webhook" className="hover:text-red-300">
                    <Trash2 />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default function DevelopersPage() {
  const { org, can } = useSession();
  const hasAccess = org?.plan === "team" || org?.plan === "enterprise";
  return (
    <>
      <PageHeader title="Developers" description="Connect Survey Agent to your stack with the REST API and webhooks." />
      {!can("admin") ? (
        <EmptyState icon={<KeyRound />} title="Admins only" description="Ask a workspace admin to manage API keys and webhooks." />
      ) : !hasAccess ? (
        <UpgradeCallout feature="The REST API and webhooks" plan="Team" />
      ) : (
        <div className="space-y-6">
          <ApiKeys />
          <Webhooks />
        </div>
      )}
    </>
  );
}
