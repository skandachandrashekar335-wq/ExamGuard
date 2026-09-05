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

export interface SecurityEvent {
  id: number;
  event_type: string;
  severity: string;
  entity_type: string;
  entity_id: number;
  entry_verification_id: number | null;
  student_id: number | null;
  exam_id: number | null;
  hall_id: number | null;
  entry_point_id: number | null;
  description: string | null;
  metadata_json: string | null;
  source: string;
  created_at: string;
}

export interface SecurityEventListResponse {
  items: SecurityEvent[];
  total: number;
  page: number;
  page_size: number;
}

export async function listSecurityEvents(params: {
  page?: number;
  page_size?: number;
  event_type?: string;
  severity?: string;
  entity_type?: string;
  student_id?: number;
  exam_id?: number;
  hall_id?: number;
  source?: string;
}): Promise<SecurityEventListResponse> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  if (params.event_type) sp.set("event_type", params.event_type);
  if (params.severity) sp.set("severity", params.severity);
  if (params.entity_type) sp.set("entity_type", params.entity_type);
  if (params.student_id) sp.set("student_id", String(params.student_id));
  if (params.exam_id) sp.set("exam_id", String(params.exam_id));
  if (params.hall_id) sp.set("hall_id", String(params.hall_id));
  if (params.source) sp.set("source", params.source);
  const qs = sp.toString();
  return request(`/api/v1/security-events${qs ? `?${qs}` : ""}`);
}

export async function getSecurityEvent(id: number): Promise<SecurityEvent> {
  return request(`/api/v1/security-events/${id}`);
}
