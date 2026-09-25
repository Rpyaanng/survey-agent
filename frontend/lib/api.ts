// Thin fetch wrapper for the Flask API. All requests go through the same-origin
// /api proxy (next.config.ts), so the httpOnly session cookie rides along.

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isPlanLimit() {
    return this.code === "plan_limit";
  }

  get requiredPlan(): string | undefined {
    return (this.details as { required_plan?: string } | undefined)?.required_plan;
  }
}

const ORG_KEY = "sa_org";

export function getActiveOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ORG_KEY);
}

export function setActiveOrgId(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(ORG_KEY, id);
  else window.localStorage.removeItem(ORG_KEY);
}

type Options = Omit<RequestInit, "body"> & { body?: unknown; responseToken?: string };

export async function api<T = unknown>(path: string, { body, headers, responseToken, ...init }: Options = {}): Promise<T> {
  const finalHeaders = new Headers(headers);
  // Custom header required by the API's CSRF check on cookie-authenticated writes.
  finalHeaders.set("X-Requested-With", "fetch");
  const orgId = getActiveOrgId();
  if (orgId) finalHeaders.set("X-Org-Id", orgId);
  if (responseToken) finalHeaders.set("X-Response-Token", responseToken);

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }

  const res = await fetch(`/api/v1${path}`, { ...init, headers: finalHeaders, body: payload, credentials: "include" });
  if (res.status === 204) return undefined as T;

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : undefined;
  if (!res.ok) {
    const err = data?.error ?? {};
    throw new ApiError(err.message ?? `Request failed (${res.status})`, res.status, err.code ?? "error", err.details);
  }
  return data as T;
}

export const fetcher = <T,>(path: string) => api<T>(path);

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}
