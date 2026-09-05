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

export interface ExaminationSession {
  id: number;
  exam_id: number;
  exam_hall_id: number;
  status: string;
  gate_status: string;
  gate_open_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  expected_capacity: number | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExaminationSessionListResponse {
  items: ExaminationSession[];
  total: number;
  page: number;
  page_size: number;
}

export interface GateEvent {
  id: number;
  session_id: number;
  previous_status: string;
  new_status: string;
  reason: string | null;
  performed_by: string | null;
  created_at: string;
}

export interface GateEventListResponse {
  items: GateEvent[];
  total: number;
}

export interface SessionSummary {
  total_sessions: number;
  not_started: number;
  in_progress: number;
  completed: number;
  cancelled: number;
  total_entry_verifications: number;
  total_attendance_records: number;
}

export async function listSessions(params: {
  page?: number;
  page_size?: number;
  exam_id?: number;
  exam_hall_id?: number;
  status?: string;
}): Promise<ExaminationSessionListResponse> {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.page_size) sp.set("page_size", String(params.page_size));
  if (params.exam_id) sp.set("exam_id", String(params.exam_id));
  if (params.exam_hall_id) sp.set("exam_hall_id", String(params.exam_hall_id));
  if (params.status) sp.set("status", params.status);
  const qs = sp.toString();
  return request(`/api/v1/examination-sessions${qs ? `?${qs}` : ""}`);
}

export async function getSession(id: number): Promise<ExaminationSession> {
  return request(`/api/v1/examination-sessions/${id}`);
}

export async function createSession(data: {
  exam_id: number;
  exam_hall_id: number;
  expected_capacity?: number;
  notes?: string;
  created_by?: string;
}): Promise<ExaminationSession> {
  return request("/api/v1/examination-sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function startSession(
  id: number,
  performed_by?: string,
): Promise<ExaminationSession> {
  return request(`/api/v1/examination-sessions/${id}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ performed_by: performed_by || null }),
  });
}

export async function endSession(
  id: number,
  performed_by?: string,
): Promise<ExaminationSession> {
  return request(`/api/v1/examination-sessions/${id}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ performed_by: performed_by || null }),
  });
}

export async function cancelSession(
  id: number,
  reason?: string,
  performed_by?: string,
): Promise<ExaminationSession> {
  return request(`/api/v1/examination-sessions/${id}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null, performed_by: performed_by || null }),
  });
}

export async function closeGates(
  id: number,
  reason?: string,
  performed_by?: string,
): Promise<ExaminationSession> {
  return request(`/api/v1/examination-sessions/${id}/close-gates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null, performed_by: performed_by || null }),
  });
}

export async function openGates(
  id: number,
  reason?: string,
  performed_by?: string,
): Promise<ExaminationSession> {
  return request(`/api/v1/examination-sessions/${id}/open-gates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null, performed_by: performed_by || null }),
  });
}

export async function listGateEvents(sessionId: number): Promise<GateEventListResponse> {
  return request(`/api/v1/examination-sessions/${sessionId}/gate-events`);
}

export async function getSessionSummary(): Promise<SessionSummary> {
  return request("/api/v1/examination-sessions/summary");
}
