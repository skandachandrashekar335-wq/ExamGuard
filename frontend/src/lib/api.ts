/**
 * ExamGuard API Client
 *
 * Centralized HTTP client for all backend API calls.
 * Automatically includes the ExamGuard JWT token in Authorization headers.
 * Handles error responses consistently.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Production safety: warn if API_BASE points to localhost
if (typeof window !== "undefined" && process.env.NODE_ENV === "production") {
  if (API_BASE.includes("localhost") || API_BASE.includes("127.0.0.1")) {
    console.error(
      "[ExamGuard] CRITICAL: NEXT_PUBLIC_API_URL is not set. " +
      "The frontend is targeting localhost in production. " +
      "Set NEXT_PUBLIC_API_URL in your Vercel environment variables."
    );
  }
}

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

export function getAuthHeaders(): Record<string, string> {
  const token = _tokenGetter?.();
  return token ? { Authorization: `Bearer ${token}` } : {};
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

  if (!headers["Content-Type"] && init?.method && init.method !== "GET" && !(init?.body instanceof FormData)) {
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
