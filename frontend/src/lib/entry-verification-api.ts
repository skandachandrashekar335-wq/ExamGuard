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

import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

export async function listEntryVerifications(params: {
  page?: number;
  page_size?: number;
  status?: string;
  entry_point_id?: string;
  student_id?: string;
}): Promise<EntryVerificationListResponse> {
  return apiRequest(`/api/v1/entry-verifications${qs(params)}`);
}

export async function getEntryVerification(id: number): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}`);
}

export async function createEntryVerification(
  data: EntryVerificationCreate,
): Promise<EntryVerification> {
  return apiRequest("/api/v1/entry-verifications", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function beginEntryVerification(id: number): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/begin`, { method: "POST" });
}

export async function processHallTicketCheck(id: number): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/hall-ticket-check`, { method: "POST" });
}

export async function processSeatCheck(id: number): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/seat-check`, { method: "POST" });
}

export async function processIdentityCheck(
  id: number,
  identityAttemptId?: number | null,
): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/identity-check`, {
    method: "POST",
    body: JSON.stringify({ identity_attempt_id: identityAttemptId ?? null }),
  });
}

export async function evaluateEntryVerification(id: number): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/evaluate`, { method: "POST" });
}

export async function escalateEntryVerification(
  id: number,
  reason: string,
): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/escalate`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function resolveEntryVerification(
  id: number,
  granted: boolean,
  reason?: string,
): Promise<EntryVerification> {
  return apiRequest(`/api/v1/entry-verifications/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ granted, reason: reason ?? null }),
  });
}
