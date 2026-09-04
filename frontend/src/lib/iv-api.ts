import type {
  VerificationContext,
  VerificationListResponse,
  VerifyFaceResponse,
  IdentityVerificationAttempt,
} from "./types";

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

export async function listAttempts(params: {
  page?: number;
  page_size?: number;
  status?: string;
  decision?: string;
  student_id?: string;
}): Promise<VerificationListResponse> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  if (params.status) sp.set("status", params.status);
  if (params.decision) sp.set("decision", params.decision);
  if (params.student_id) sp.set("student_id", params.student_id);
  return request(`/api/v1/identity-verifications?${sp}`);
}

export async function getAttemptContext(
  id: number,
): Promise<VerificationContext> {
  return request(`/api/v1/identity-verifications/${id}/context`);
}

export async function getAttempt(
  id: number,
): Promise<{ attempt: IdentityVerificationAttempt; evidence: unknown[] }> {
  return request(`/api/v1/identity-verifications/${id}`);
}

export async function startAttempt(
  id: number,
): Promise<IdentityVerificationAttempt> {
  return request(`/api/v1/identity-verifications/${id}/start`, {
    method: "POST",
  });
}

export async function verifyFace(
  id: number,
  payload: {
    reference_image: string;
    probe_image: string;
    reference_image_format?: string;
    probe_image_format?: string;
  },
): Promise<VerifyFaceResponse> {
  return request(`/api/v1/identity-verifications/${id}/verify-face`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function evaluateEvidence(
  id: number,
): Promise<IdentityVerificationAttempt> {
  return request(`/api/v1/identity-verifications/${id}/evaluate`, {
    method: "POST",
  });
}

export async function reviewAttempt(
  id: number,
  reviewer_notes?: string,
): Promise<IdentityVerificationAttempt> {
  return request(`/api/v1/identity-verifications/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_notes: reviewer_notes || null }),
  });
}

export async function overrideDecision(
  id: number,
  payload: {
    new_decision: string;
    reason: string;
    operator_id?: string;
  },
): Promise<IdentityVerificationAttempt> {
  return request(`/api/v1/identity-verifications/${id}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function cancelAttempt(
  id: number,
): Promise<IdentityVerificationAttempt> {
  return request(`/api/v1/identity-verifications/${id}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}
