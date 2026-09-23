import { apiRequest, API_BASE, getAuthHeaders } from "./api";

export interface DemoLoadResponse {
  status: string;
  message: string;
  demo_exam_id: number;
  demo_hall_id: number;
  demo_student_ids: number[];
  demo_student_usns: string[];
  demo_session_id: number;
  demo_attempt_ids: number[];
  demo_invigilator_assignment_id: number | null;
}

export interface DemoStatusResponse {
  loaded: boolean;
  demo_exam_id: number | null;
  demo_hall_id: number | null;
  demo_student_ids: number[] | null;
  demo_student_usns: string[] | null;
  demo_student_names: string[] | null;
  demo_session_id: number | null;
  demo_attempt_ids: number[] | null;
  reference_face_urls: (string | null)[] | null;
}

export interface DemoSessionStatus {
  loaded: boolean;
  session_id: number | null;
  session_status: string | null;
  gate_status: string | null;
  exam_name: string | null;
  exam_date: string | null;
  hall_name: string | null;
  invigilator_email: string | null;
  started_at: string | null;
}

export async function getDemoStatus(): Promise<DemoStatusResponse> {
  return apiRequest<DemoStatusResponse>("/api/v1/demo/status");
}

export async function loadDemoData(): Promise<DemoLoadResponse> {
  return apiRequest<DemoLoadResponse>("/api/v1/demo/load", {
    method: "POST",
    headers: getAuthHeaders(),
  });
}

export async function resetDemoData(): Promise<{
  status: string;
  message: string;
  records_deleted: number;
}> {
  return apiRequest("/api/v1/demo/reset", {
    method: "POST",
    headers: getAuthHeaders(),
  });
}

export async function uploadDemoReferenceFace(
  attemptId: number,
  referenceImage: string,
  imageFormat: string
): Promise<{ status: string; attempt_id: number; reference_face_url: string }> {
  return apiRequest("/api/v1/demo/upload-reference-face", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      attempt_id: attemptId,
      reference_image: referenceImage,
      image_format: imageFormat,
    }),
  });
}

export async function assignDemoInvigilator(
  email: string
): Promise<{ status: string; assignment_id: number; email: string }> {
  return apiRequest("/api/v1/demo/assign-invigilator", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ email }),
  });
}

export async function startDemoSession(
  performedBy?: string
): Promise<{ status: string; session_id: number; session_status: string; gate_status: string }> {
  return apiRequest("/api/v1/demo/start-session", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ performed_by: performedBy || "admin" }),
  });
}

export async function getDemoSessionStatus(): Promise<DemoSessionStatus> {
  return apiRequest<DemoSessionStatus>("/api/v1/demo/session-status");
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
