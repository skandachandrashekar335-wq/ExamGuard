import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

export interface SecurityEvent {
  id: number; event_type: string; severity: string; entity_type: string;
  entity_id: number; entry_verification_id: number | null;
  student_id: number | null; exam_id: number | null; hall_id: number | null;
  entry_point_id: number | null; description: string | null;
  metadata_json: string | null; source: string; created_at: string;
}

export interface SecurityEventListResponse {
  items: SecurityEvent[]; total: number; page: number; page_size: number;
}

export async function listSecurityEvents(params: {
  page?: number; page_size?: number; event_type?: string; severity?: string;
  entity_type?: string; student_id?: number; exam_id?: number;
  hall_id?: number; source?: string;
}): Promise<SecurityEventListResponse> {
  return apiRequest(`/api/v1/security-events${qs(params)}`);
}

export async function getSecurityEvent(id: number): Promise<SecurityEvent> {
  return apiRequest(`/api/v1/security-events/${id}`);
}
