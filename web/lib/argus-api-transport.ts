import { getSupabaseClient } from "./supabase-client";

export const ARGUS_API_BASE_URL = (() => {
  if (process.env.NEXT_PUBLIC_ARGUS_API_URL) {
    return process.env.NEXT_PUBLIC_ARGUS_API_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }
  return "http://127.0.0.1:8000/api/v1";
})();

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const authHeaders: Record<string, string> = {};

  if (!isMockAuth) {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase auth client is unavailable in non-mock mode.");
    }
    const { data, error } = await supabase.auth.getSession();
    if (!error && data.session) {
      authHeaders.Authorization = `Bearer ${data.session.access_token}`;
    }
  }

  const response = await fetch(`${ARGUS_API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(options?.headers || {}),
    },
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    const errorMsg =
      typeof detail === "object" && detail !== null
        ? ((detail as { title?: unknown }).title as string)
        : detail;

    const error = new Error(
      (errorMsg as string) ?? `API error ${response.status}`,
    ) as Error & { status: number; code: string };
    error.status = response.status;
    error.code =
      ((body as Record<string, unknown>).code as string) ?? "unknown";
    throw error;
  }
  return response.json() as Promise<T>;
}

export async function unauthenticatedApiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${ARGUS_API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail?: unknown }).detail ?? "")
        : typeof detail === "string"
          ? detail
          : `API error ${response.status}`;
    const error = new Error(message) as Error & {
      status: number;
      code: string;
    };
    error.status = response.status;
    error.code = String((body as Record<string, unknown>).code ?? "unknown");
    throw error;
  }
  return response.json() as Promise<T>;
}
