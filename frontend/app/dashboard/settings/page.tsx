"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Field, PageHeader, notifyError } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

function Card({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="glass-panel rounded-2xl p-6">
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-ink-muted">{description}</p>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function OrganizationCard() {
  const { org, can, refresh } = useSession();
  const [name, setName] = useState(org?.name ?? "");
  const [color, setColor] = useState(org?.branding.primary_color ?? "#3b82f6");
  const [logo, setLogo] = useState(org?.branding.logo_url ?? "");
  const [saving, setSaving] = useState(false);
  const readOnly = !can("admin");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api("/org", { method: "PATCH", body: { name, branding: { primary_color: color, logo_url: logo || null } } });
      await refresh();
      toast.success("Workspace updated");
    } catch (err) {
      notifyError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Workspace" description="Your organization's name and the branding respondents see on survey pages.">
      <form onSubmit={save} className="space-y-5">
        <fieldset disabled={readOnly} className="space-y-5">
          <Field label="Workspace name" htmlFor="org-name">
            <Input id="org-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <div className="grid gap-5 sm:grid-cols-[1fr_180px]">
            <Field label="Logo URL" htmlFor="logo" hint="A square or wide PNG/SVG hosted on HTTPS.">
              <Input id="logo" type="url" value={logo} onChange={(e) => setLogo(e.target.value)} placeholder="https://…/logo.svg" />
            </Field>
            <Field label="Brand color" htmlFor="color">
              <div className="flex gap-2">
                <input
                  id="color"
                  type="color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  className="h-10 w-12 cursor-pointer rounded-lg border border-white/10 bg-transparent"
                />
                <Input value={color} onChange={(e) => setColor(e.target.value)} pattern="^#[0-9a-fA-F]{6}$" className="font-mono" aria-label="Brand color hex" />
              </div>
            </Field>
          </div>
        </fieldset>
        {!readOnly && (
          <div className="flex justify-end">
            <Button type="submit" loading={saving}>
              Save workspace
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}

function ProfileCard() {
  const { session, refresh } = useSession();
  const [name, setName] = useState(session?.user.name ?? "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [saving, setSaving] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api("/auth/me", {
        method: "PATCH",
        body: { name, ...(next ? { current_password: current, new_password: next } : {}) },
      });
      await refresh();
      setCurrent("");
      setNext("");
      toast.success("Profile updated");
    } catch (err) {
      notifyError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Your profile" description={session?.user.email ?? ""}>
      <form onSubmit={save} className="space-y-5">
        <Field label="Name" htmlFor="name">
          <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Current password" htmlFor="current">
            <Input id="current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <Field label="New password" htmlFor="new" hint="Leave blank to keep your current password.">
            <Input id="new" type="password" autoComplete="new-password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
        </div>
        <div className="flex justify-end">
          <Button type="submit" loading={saving}>
            Save profile
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default function SettingsPage() {
  const { org } = useSession();
  return (
    <>
      <PageHeader title="Settings" description="Manage your workspace and account." />
      <div className="space-y-6">
        {org && <OrganizationCard key={org.id} />}
        <ProfileCard />
      </div>
    </>
  );
}
