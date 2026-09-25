"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";
import useSWR, { useSWRConfig } from "swr";
import { useRouter } from "next/navigation";
import { api, getActiveOrgId, setActiveOrgId } from "./api";
import type { Organization, Session } from "./types";

interface SessionContextValue {
  session: Session | undefined;
  org: Organization | undefined;
  isLoading: boolean;
  switchOrg: (orgId: string) => void;
  refresh: () => Promise<unknown>;
  logout: () => Promise<void>;
  can: (role: Organization["role"]) => boolean;
}

const RANK: Record<Organization["role"], number> = { viewer: 0, editor: 1, admin: 2, owner: 3 };

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { mutate: globalMutate } = useSWRConfig();
  const { data: session, isLoading, mutate, error } = useSWR<Session>("/auth/me", { shouldRetryOnError: false });

  useEffect(() => {
    if (!error) return;
    // Clear the stale cookie first, otherwise proxy.ts would bounce /login back here.
    const next = encodeURIComponent(window.location.pathname);
    api("/auth/logout", { method: "POST" })
      .catch(() => undefined)
      .finally(() => router.replace(`/login?next=${next}`));
  }, [error, router]);

  const org = useMemo(() => {
    if (!session) return undefined;
    const stored = getActiveOrgId();
    return (
      session.organizations.find((o) => o.id === stored) ??
      session.organizations.find((o) => o.id === session.default_org_id) ??
      session.organizations[0]
    );
  }, [session]);

  // Keep the header the API reads in sync with the org we resolved.
  useEffect(() => {
    if (org && getActiveOrgId() !== org.id) setActiveOrgId(org.id);
  }, [org]);

  const switchOrg = useCallback(
    (orgId: string) => {
      setActiveOrgId(orgId);
      // Every cached query is org-scoped; drop them all.
      globalMutate(() => true, undefined, { revalidate: true });
      router.push("/dashboard");
    },
    [globalMutate, router],
  );

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    setActiveOrgId(null);
    globalMutate(() => true, undefined, { revalidate: false });
    router.replace("/login");
  }, [globalMutate, router]);

  const can = useCallback((role: Organization["role"]) => (org ? RANK[org.role] >= RANK[role] : false), [org]);

  return (
    <SessionContext.Provider value={{ session, org, isLoading, switchOrg, refresh: mutate, logout, can }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
