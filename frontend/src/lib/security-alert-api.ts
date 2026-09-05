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

export interface SecurityAlert {
  id: number;
  security_event_id: number;
  status: string;
  severity: string;
  message: string;
  assigned_to: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SecurityAlertListResponse {
  items: SecurityAlert[];
  total: number;
  page: number;
  page_size: number;
}

export async function listSecurityAlerts(params: {
  page?: number;
  page_size?: number;
  status?: string;
  severity?: string;
  security_event_id?: number;
}): Promise<SecurityAlertListResponse> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  if (params.status) sp.set("status", params.status);
  if (params.severity) sp.set("severity", params.severity);
  if (params.security_event_id) sp.set("security_event_id", String(params.security_event_id));
  const qs = sp.toString();
  return request(`/api/v1/security-alerts${qs ? `?${qs}` : ""}`);
}

export async function getSecurityAlert(id: number): Promise<SecurityAlert> {
  return request(`/api/v1/security-alerts/${id}`);
}

export async function acknowledgeAlert(
  id: number,
  assignedTo?: string,
): Promise<SecurityAlert> {
  return request(`/api/v1/security-alerts/${id}/acknowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assigned_to: assignedTo || null }),
  });
}

export async function resolveAlert(
  id: number,
  resolutionNotes?: string,
  assignedTo?: string,
): Promise<SecurityAlert> {
  return request(`/api/v1/security-alerts/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resolution_notes: resolutionNotes || null,
      assigned_to: assignedTo || null,
    }),
  });
}

export async function dismissAlert(
  id: number,
  reason: string,
  assignedTo?: string,
): Promise<SecurityAlert> {
  return request(`/api/v1/security-alerts/${id}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, assigned_to: assignedTo || null }),
  });
}
