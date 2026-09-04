export interface EntryVerification {
  id: number;
  student_id: number;
  exam_registration_id: number;
  exam_hall_id: number;
  entry_point_id: number;
  camera_id: number | null;
  hall_ticket_id: number | null;
  identity_verification_attempt_id: number | null;
  status: string;
  hall_ticket_check: string;
  identity_check: string;
  seat_check: string;
  escalation_reason: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EntryVerificationListResponse {
  items: EntryVerification[];
  total: number;
  page: number;
  page_size: number;
}

export interface EntryVerificationCreate {
  student_id: number;
  exam_registration_id: number;
  entry_point_id: number;
  camera_id?: number | null;
  hall_ticket_id?: number | null;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }
  return res.json();
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

export async function listEntryVerifications(params: {
  page?: number;
  page_size?: number;
  status?: string;
  entry_point_id?: string;
  student_id?: string;
}): Promise<EntryVerificationListResponse> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  if (params.status) sp.set("status", params.status);
  if (params.entry_point_id) sp.set("entry_point_id", params.entry_point_id);
  if (params.student_id) sp.set("student_id", params.student_id);
  return request(`/api/v1/entry-verifications?${sp}`);
}

export async function getEntryVerification(
  id: number,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}`);
}

export async function createEntryVerification(
  data: EntryVerificationCreate,
): Promise<EntryVerification> {
  return request("/api/v1/entry-verifications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function beginEntryVerification(
  id: number,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/begin`, {
    method: "POST",
  });
}

export async function processHallTicketCheck(
  id: number,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/hall-ticket-check`, {
    method: "POST",
  });
}

export async function processSeatCheck(
  id: number,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/seat-check`, {
    method: "POST",
  });
}

export async function processIdentityCheck(
  id: number,
  identityAttemptId?: number | null,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/identity-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identity_attempt_id: identityAttemptId ?? null }),
  });
}

export async function evaluateEntryVerification(
  id: number,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/evaluate`, {
    method: "POST",
  });
}

export async function escalateEntryVerification(
  id: number,
  reason: string,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/escalate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
}

export async function resolveEntryVerification(
  id: number,
  granted: boolean,
  reason?: string,
): Promise<EntryVerification> {
  return request(`/api/v1/entry-verifications/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ granted, reason: reason ?? null }),
  });
}
