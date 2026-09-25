"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { api, errorMessage, setActiveOrgId } from "@/lib/api";
import type { Organization, Session } from "@/lib/types";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const { data: invite, error } = useSWR<{ email: string; role: string; organization: string }>(`/invitations/${token}`);
  const { data: session } = useSWR<Session>("/auth/me", { shouldRetryOnError: false });
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  async function accept() {
    setAccepting(true);
    setAcceptError(null);
    try {
      const org = await api<Organization>(`/invitations/${token}/accept`, { method: "POST" });
      setActiveOrgId(org.id);
      router.replace("/dashboard");
    } catch (err) {
      setAcceptError(errorMessage(err));
      setAccepting(false);
    }
  }

  if (error) {
    return (
      <AuthShell title="Invitation not found" subtitle="This invitation has expired or was already used.">
        <Button asChild className="w-full">
          <Link href="/login">Go to sign in</Link>
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={invite ? `Join ${invite.organization}` : "Loading invitation…"}
      subtitle={invite ? `You've been invited as ${invite.role} (${invite.email}).` : undefined}
    >
      {session ? (
        <div className="space-y-3">
          <p className="text-sm text-ink-muted">
            Signed in as <span className="text-ink">{session.user.email}</span>.
          </p>
          {acceptError && <p className="text-sm text-red-300">{acceptError}</p>}
          <Button className="w-full" size="lg" loading={accepting} onClick={accept} disabled={!invite}>
            Accept invitation
          </Button>
        </div>
      ) : (
        <div className="grid gap-3">
          <Button asChild size="lg">
            <Link href={`/signup?invite=${token}`}>Create an account</Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link href={`/login?next=/invite/${token}`}>I already have an account</Link>
          </Button>
        </div>
      )}
    </AuthShell>
  );
}
