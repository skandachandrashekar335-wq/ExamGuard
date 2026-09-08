/**
 * ExamGuard API Client
 *
 * Centralized HTTP client for all backend API calls.
 * Automatically includes the ExamGuard JWT token in Authorization headers.
 * Handles error responses consistently.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _tokenGetter: (() => string | null) | null = null;

export function setTokenGetter(getter: () => string | null) {
  _tokenGetter = getter;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = _tokenGetter?.();
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (!headers["Content-Type"] && init?.method && init.method !== "GET") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}
