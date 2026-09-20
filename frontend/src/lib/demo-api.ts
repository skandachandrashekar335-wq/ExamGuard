import { apiRequest, API_BASE, getAuthHeaders } from "./api";

export interface DemoLoadResponse {
  status: string;
  message: string;
  demo_exam_id: number;
  demo_hall_id: number;
  demo_student_id: number;
  demo_session_id: number;
  demo_attempt_id: number;
  demo_invigilator_assignment_id: number | null;
}

export interface DemoStatusResponse {
  loaded: boolean;
  demo_exam_id: number | null;
  demo_hall_id: number | null;
  demo_student_id: number | null;
  demo_session_id: number | null;
  demo_attempt_id: number | null;
}

export async function getDemoStatus(): Promise<DemoStatusResponse> {
  return apiRequest<DemoStatusResponse>("/api/v1/demo/status");
}

export async function loadDemoData(): Promise<DemoLoadResponse> {
  return apiRequest<DemoLoadResponse>("/api/v1/demo/load", {
    method: "POST",
  });
}

export async function resetDemoData(): Promise<{
  status: string;
  message: string;
  records_deleted: number;
}> {
  return apiRequest("/api/v1/demo/reset", { method: "POST" });
}

export async function getDemoReferenceImageBlob(): Promise<Blob> {
  const headers = getAuthHeaders();
  const res = await fetch(`${API_BASE}/api/v1/demo/reference-image`, {
    headers,
  });
  if (res.status === 403) throw new Error("Demo reference image requires Administrator or Operator access.");
  if (!res.ok) throw new Error("Failed to load demo reference image");
  return res.blob();
}
