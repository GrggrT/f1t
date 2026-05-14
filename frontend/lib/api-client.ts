// Client-side fetch wrapper that injects the user's backend JWT
// (NextAuth session.user.backendToken) as `Authorization: Bearer ...`.
//
// Browser code uses NEXT_PUBLIC_API_URL; the Docker-internal `API_URL` is
// for server components only, which should keep using fetch in lib/api.ts.

import { getSession } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = path.startsWith("http") ? path : `${API}${path}`;
  const session = await getSession();
  const headers = new Headers(init.headers);

  if (session?.user?.backendToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${session.user.backendToken}`);
  }

  if (
    init.body &&
    !headers.has("Content-Type") &&
    typeof init.body === "string"
  ) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(url, { ...init, headers });
}

export async function apiFetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}
