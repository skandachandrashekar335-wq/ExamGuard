export interface SecuritySignal {
  id: number;
  entry_verification_id: number;
  signal_type: string;
  strength: string;
  source: string;
  description: string | null;
  created_at: string;
}

export interface SecuritySignalListResponse {
  items: SecuritySignal[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProxyRiskAssessment {
  id: number;
  entry_verification_id: number;
  risk_level: string;
  risk_score: number;
  signal_count: number | null;
  strong_signal_count: number | null;
  explanation: string | null;
  policy_version: string | null;
  assessed_at: string;
}

export interface ProxyRiskAssessmentListResponse {
  items: ProxyRiskAssessment[];
  total: number;
  page: number;
  page_size: number;
}

import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

export async function detectSignals(entryVerificationId: number): Promise<SecuritySignal[]> {
  return apiRequest(`/api/v1/entry-verifications/${entryVerificationId}/risk/signals/detect`, {
    method: "POST",
  });
}

export async function listSignals(
  entryVerificationId: number,
  params?: { page?: number; page_size?: number },
): Promise<SecuritySignalListResponse> {
  return apiRequest(`/api/v1/entry-verifications/${entryVerificationId}/risk/signals${qs(params || {})}`);
}

export async function assessRisk(entryVerificationId: number): Promise<ProxyRiskAssessment> {
  return apiRequest(`/api/v1/entry-verifications/${entryVerificationId}/risk/assess`, {
    method: "POST",
  });
}

export async function listAssessments(
  entryVerificationId: number,
  params?: { page?: number; page_size?: number },
): Promise<ProxyRiskAssessmentListResponse> {
  return apiRequest(`/api/v1/entry-verifications/${entryVerificationId}/risk/assessments${qs(params || {})}`);
}

export async function getLatestAssessment(entryVerificationId: number): Promise<ProxyRiskAssessment> {
  return apiRequest(`/api/v1/entry-verifications/${entryVerificationId}/risk`);
}
