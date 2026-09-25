"use client";

import { useState } from "react";
import useSWR from "swr";
import { MailPlus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { CopyButton, PageHeader, notifyError } from "@/components/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { timeAgo } from "@/lib/utils";
import type { Invitation, Member, Role } from "@/lib/types";

const ROLE_HELP: Record<Role, string> = {
  owner: "Full control, including billing and deleting the workspace",
  admin: "Manage members, billing, API keys and webhooks",
  editor: "Create, edit and publish surveys",
  viewer: "View surveys, responses and analytics",
};

export default function TeamPage() {
  const { session, can } = useSession();
  const { data, mutate } = useSWR<{ members: Member[]; invitations: Invitation[] }>("/org/members");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [inviting, setInviting] = useState(false);
  const [lastLink, setLastLink] = useState<string | null>(null);
  const isAdmin = can("admin");

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    try {
      const inv = await api<Invitation>("/org/invitations", { method: "POST", body: { email, role } });
      setLastLink(inv.accept_link ?? null);
      setEmail("");
      toast.success(`Invitation sent to ${inv.email}`);
      mutate();
    } catch (err) {
      notifyError(err);
    } finally {
      setInviting(false);
    }
  }

  async function changeRole(member: Member, next: Role) {
    try {
      await api(`/org/members/${member.id}`, { method: "PATCH", body: { role: next } });
      mutate();
    } catch (err) {
      notifyError(err);
    }
  }

  async function remove(member: Member) {
    if (!window.confirm(`Remove ${member.user.email} from this workspace?`)) return;
    try {
      await api(`/org/members/${member.id}`, { method: "DELETE" });
      mutate();
    } catch (err) {
      notifyError(err);
    }
  }

  async function revoke(inv: Invitation) {
    try {
      await api(`/org/invitations/${inv.id}`, { method: "DELETE" });
      mutate();
    } catch (err) {
      notifyError(err);
    }
  }

  return (
    <>
      <PageHeader title="Team" description="Invite teammates and control what they can do." />
      {isAdmin && (
        <section className="glass-panel mb-6 rounded-2xl p-6">
          <form onSubmit={invite} className="flex flex-col gap-3 sm:flex-row">
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" className="flex-1" aria-label="Email" />
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)} className="sm:w-36" aria-label="Role">
              <option value="admin">Admin</option>
              <option value="editor">Editor</option>
              <option value="viewer">Viewer</option>
            </Select>
            <Button type="submit" loading={inviting}>
              <MailPlus /> Invite
            </Button>
          </form>
          <p className="mt-2 text-xs text-ink-faint">{ROLE_HELP[role]}.</p>
          {lastLink && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-white/[0.03] p-3">
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink-muted">{lastLink}</span>
              <CopyButton value={lastLink} label="Copy invite link" />
            </div>
          )}
        </section>
      )}

      {!data ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : (
        <div className="glass-panel overflow-hidden rounded-2xl">
          <ul className="divide-y divide-white/[0.06]">
            {data.members.map((m) => {
              const isMe = m.user.id === session?.user.id;
              return (
                <li key={m.id} className="flex flex-col gap-3 px-6 py-4 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-xs font-semibold text-ink">
                      {(m.user.name || m.user.email).slice(0, 2).toUpperCase()}
                    </span>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-ink">
                        {m.user.name} {isMe && <span className="text-ink-faint">(you)</span>}
                      </div>
                      <div className="truncate text-xs text-ink-faint">{m.user.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {isAdmin && !isMe ? (
                      <Select value={m.role} onChange={(e) => changeRole(m, e.target.value as Role)} className="h-9 w-32" aria-label="Role">
                        {(can("owner") ? ["owner", "admin", "editor", "viewer"] : ["admin", "editor", "viewer"]).map((r) => (
                          <option key={r} value={r} className="capitalize">
                            {r}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <Badge className="capitalize">{m.role}</Badge>
                    )}
                    {isAdmin && !isMe && (
                      <Button variant="ghost" size="icon" onClick={() => remove(m)} aria-label="Remove member" className="hover:text-red-300">
                        <Trash2 />
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
            {data.invitations.map((inv) => (
              <li key={inv.id} className="flex items-center gap-3 px-6 py-4">
                <span className="flex h-9 w-9 items-center justify-center rounded-full border border-dashed border-white/15">
                  <MailPlus className="h-4 w-4 text-ink-faint" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm text-ink-muted">{inv.email}</div>
                  <div className="text-xs text-ink-faint">Invited {timeAgo(inv.created_at)} as {inv.role}</div>
                </div>
                <Badge tone="info">Pending</Badge>
                {isAdmin && (
                  <Button variant="ghost" size="sm" onClick={() => revoke(inv)}>
                    Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
