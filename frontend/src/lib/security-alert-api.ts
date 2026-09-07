import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

export interface SecurityAlert {
  id: number; security_event_id: number; status: string; severity: string;
  message: string; assigned_to: string | null; acknowledged_at: string | null;
  resolved_at: string | null; resolution_notes: string | null;
  created_at: string; updated_at: string;
}

export interface SecurityAlertListResponse {
  items: SecurityAlert[]; total: number; page: number; page_size: number;
}

export async function listSecurityAlerts(params: {
  page?: number; page_size?: number; status?: string;
  severity?: string; security_event_id?: number;
}): Promise<SecurityAlertListResponse> {
  return apiRequest(`/api/v1/security-alerts${qs(params)}`);
}

export async function getSecurityAlert(id: number): Promise<SecurityAlert> {
  return apiRequest(`/api/v1/security-alerts/${id}`);
}

export async function acknowledgeAlert(id: number, assignedTo?: string): Promise<SecurityAlert> {
  return apiRequest(`/api/v1/security-alerts/${id}/acknowledge`, {
    method: "POST",
    body: JSON.stringify({ assigned_to: assignedTo || null }),
  });
}

export async function resolveAlert(
  id: number, resolutionNotes?: string, assignedTo?: string,
): Promise<SecurityAlert> {
  return apiRequest(`/api/v1/security-alerts/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution_notes: resolutionNotes || null, assigned_to: assignedTo || null }),
  });
}

export async function dismissAlert(
  id: number, reason: string, assignedTo?: string,
): Promise<SecurityAlert> {
  return apiRequest(`/api/v1/security-alerts/${id}/dismiss`, {
    method: "POST",
    body: JSON.stringify({ reason, assigned_to: assignedTo || null }),
  });
}
