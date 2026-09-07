import type {
  VerificationContext,
  VerificationListResponse,
  VerifyFaceResponse,
  IdentityVerificationAttempt,
} from "./types";

import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

export async function listAttempts(params: {
  page?: number;
  page_size?: number;
  status?: string;
  decision?: string;
  student_id?: string;
}): Promise<VerificationListResponse> {
  return apiRequest(`/api/v1/identity-verifications${qs(params)}`);
}

export async function getAttemptContext(id: number): Promise<VerificationContext> {
  return apiRequest(`/api/v1/identity-verifications/${id}/context`);
}

export async function getAttempt(
  id: number,
): Promise<{ attempt: IdentityVerificationAttempt; evidence: unknown[] }> {
  return apiRequest(`/api/v1/identity-verifications/${id}`);
}

export async function startAttempt(id: number): Promise<IdentityVerificationAttempt> {
  return apiRequest(`/api/v1/identity-verifications/${id}/start`, { method: "POST" });
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
  return apiRequest(`/api/v1/identity-verifications/${id}/verify-face`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function evaluateEvidence(id: number): Promise<IdentityVerificationAttempt> {
  return apiRequest(`/api/v1/identity-verifications/${id}/evaluate`, { method: "POST" });
}

export async function reviewAttempt(
  id: number,
  reviewer_notes?: string,
): Promise<IdentityVerificationAttempt> {
  return apiRequest(`/api/v1/identity-verifications/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ reviewer_notes: reviewer_notes || null }),
  });
}

export async function overrideDecision(
  id: number,
  payload: { new_decision: string; reason: string; operator_id?: string },
): Promise<IdentityVerificationAttempt> {
  return apiRequest(`/api/v1/identity-verifications/${id}/override`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelAttempt(id: number): Promise<IdentityVerificationAttempt> {
  return apiRequest(`/api/v1/identity-verifications/${id}/cancel`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
