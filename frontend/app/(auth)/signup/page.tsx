"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Check } from "lucide-react";
import { AuthShell } from "@/components/auth-shell";
import { Field } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api, errorMessage, setActiveOrgId } from "@/lib/api";
import type { Session } from "@/lib/types";

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const invite = params.get("invite");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setLoading(true);
    setErrors({});
    setFormError(null);
    try {
      const session = await api<Session>("/auth/register", {
        method: "POST",
        body: {
          name: form.get("name"),
          email: form.get("email"),
          password: form.get("password"),
          organization_name: form.get("organization_name"),
        },
      });
      setActiveOrgId(session.default_org_id);
      router.replace(invite ? `/invite/${invite}` : "/dashboard/surveys/new");
    } catch (err) {
      if (err instanceof ApiError && err.code === "validation_error" && Array.isArray(err.details)) {
        setErrors(Object.fromEntries((err.details as { field: string; message: string }[]).map((d) => [d.field, d.message])));
      } else {
        setFormError(errorMessage(err));
      }
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Your name" htmlFor="name" error={errors.name}>
          <Input id="name" name="name" autoComplete="name" required />
        </Field>
        <Field label="Company" htmlFor="organization_name" error={errors.organization_name}>
          <Input id="organization_name" name="organization_name" autoComplete="organization" placeholder="Optional" />
        </Field>
      </div>
      <Field label="Work email" htmlFor="email" error={errors.email}>
        <Input id="email" name="email" type="email" autoComplete="email" required />
      </Field>
      <Field label="Password" htmlFor="password" hint="At least 8 characters" error={errors.password}>
        <Input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
      </Field>
      {formError && <p className="rounded-lg border border-red-400/20 bg-red-500/10 px-3 py-2 text-sm text-red-300">{formError}</p>}
      <Button type="submit" className="w-full" size="lg" loading={loading}>
        Create free account
      </Button>
      <ul className="space-y-1.5 pt-1 text-xs text-ink-faint">
        {["Free forever plan, no credit card", "Form and AI chat interviews included"].map((t) => (
          <li key={t} className="flex items-center gap-2">
            <Check className="h-3.5 w-3.5 text-emerald-400" />
            {t}
          </li>
        ))}
      </ul>
    </form>
  );
}

export default function SignupPage() {
  return (
    <AuthShell
      title="Start collecting better answers"
      subtitle="Create your workspace in under a minute."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-cyan-400 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <Suspense>
        <SignupForm />
      </Suspense>
    </AuthShell>
  );
}
