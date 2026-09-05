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

export async function detectSignals(
  entryVerificationId: number,
): Promise<SecuritySignal[]> {
  return request(`/api/v1/entry-verifications/${entryVerificationId}/risk/signals/detect`, {
    method: "POST",
  });
}

export async function listSignals(
  entryVerificationId: number,
  params?: { page?: number; page_size?: number },
): Promise<SecuritySignalListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  const qs = sp.toString();
  return request(`/api/v1/entry-verifications/${entryVerificationId}/risk/signals${qs ? `?${qs}` : ""}`);
}

export async function assessRisk(
  entryVerificationId: number,
): Promise<ProxyRiskAssessment> {
  return request(`/api/v1/entry-verifications/${entryVerificationId}/risk/assess`, {
    method: "POST",
  });
}

export async function listAssessments(
  entryVerificationId: number,
  params?: { page?: number; page_size?: number },
): Promise<ProxyRiskAssessmentListResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  const qs = sp.toString();
  return request(`/api/v1/entry-verifications/${entryVerificationId}/risk/assessments${qs ? `?${qs}` : ""}`);
}

export async function getLatestAssessment(
  entryVerificationId: number,
): Promise<ProxyRiskAssessment> {
  return request(`/api/v1/entry-verifications/${entryVerificationId}/risk`);
}
