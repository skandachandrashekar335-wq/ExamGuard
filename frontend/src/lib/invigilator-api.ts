import { apiRequest } from "./api";
export { ApiError } from "./api";

export interface InvigilatorProfile {
  user_id: number; email: string | null; full_name: string | null; role: string;
  assignment_id: number; exam_id: number; exam_name: string;
  exam_date: string; exam_start_time: string; exam_end_time: string;
  subject_code: string | null; subject_name: string | null;
  hall_id: number; hall_name: string; hall_building: string; hall_room: string;
  entry_point_id: number | null; entry_point_name: string | null;
  entry_point_code: string | null; camera_id: number | null;
  camera_name: string | null; camera_status: string | null;
  session_id: number | null; session_status: string | null;
  gate_status: string | null;
}

export interface InvigilatorDashboard {
  profile: InvigilatorProfile;
  session_active: boolean; can_start: boolean; can_end: boolean;
  verification_count: number; granted_count: number;
  denied_count: number; escalated_count: number;
  attendance_count: number; security_event_count: number;
  recent_verifications: Record<string, unknown>[];
}

export interface InvigilatorAssignment {
  id: number; user_id: number; exam_id: number; exam_hall_id: number;
  entry_point_id: number | null; camera_id: number | null;
  is_active: boolean; notes: string | null;
  created_at: string; updated_at: string;
  user_email: string | null; user_name: string | null;
  exam_name: string | null; hall_name: string | null;
}

export async function getInvigilatorProfile(): Promise<InvigilatorProfile> {
  return apiRequest("/api/v1/invigilator/profile");
}

export async function getInvigilatorDashboard(): Promise<InvigilatorDashboard> {
  return apiRequest("/api/v1/invigilator/dashboard");
}

export async function startExam(performed_by?: string): Promise<{ status: string; session_id: number; gate_status: string }> {
  return apiRequest("/api/v1/invigilator/start-exam", {
    method: "POST",
    body: JSON.stringify({ performed_by: performed_by || null }),
  });
}

export async function endExam(performed_by?: string): Promise<{ status: string; session_id: number }> {
  return apiRequest("/api/v1/invigilator/end-exam", {
    method: "POST",
    body: JSON.stringify({ performed_by: performed_by || null }),
  });
}

export async function listInvigilatorAssignments(params: {
  page?: number; page_size?: number; user_id?: number;
  exam_id?: number; exam_hall_id?: number; include_inactive?: boolean;
} = {}): Promise<{ items: InvigilatorAssignment[]; total: number; page: number; page_size: number }> {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) sp.set(k, String(v));
  }
  const s = sp.toString();
  return apiRequest(`/api/v1/invigilator-assignments${s ? `?${s}` : ""}`);
}

export async function createInvigilatorAssignment(data: {
  user_id: number; exam_id: number; exam_hall_id: number;
  entry_point_id?: number | null; camera_id?: number | null; notes?: string | null;
}): Promise<InvigilatorAssignment> {
  return apiRequest("/api/v1/invigilator-assignments", {
    method: "POST", body: JSON.stringify(data),
  });
}
