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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EventType =
  | "ENTRY_CREATED"
  | "ENTRY_BEGAN"
  | "ENTRY_GRANTED"
  | "ENTRY_DENIED"
  | "ENTRY_ESCALATED"
  | "ENTRY_RESOLVED"
  | "SIGNAL_DETECTED"
  | "RISK_ASSESSED"
  | "RISK_ELEVATED"
  | "RISK_HIGH"
  | "RISK_CRITICAL"
  | "ATTENDANCE_RECORDED"
  | "ATTENDANCE_CORRECTED"
  | "CAMERA_ONLINE"
  | "CAMERA_OFFLINE"
  | "HEARTBEAT";

export type EventCategory =
  | "ENTRY"
  | "RISK"
  | "ATTENDANCE"
  | "CAMERA"
  | "SYSTEM";

export type EventSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface MonitoringEvent {
  event_id: string;
  event_type: EventType;
  category: EventCategory;
  severity: EventSeverity;
  entity_type: string;
  entity_id: number;
  timestamp: string;
  exam_id: number | null;
  hall_id: number | null;
  student_id: number | null;
  entry_point_id: number | null;
  payload: Record<string, unknown>;
}

export interface MonitoringAlert {
  alert_id: string;
  event_id: string;
  event_type: EventType;
  severity: EventSeverity;
  entity_type: string;
  entity_id: number;
  exam_id: number | null;
  hall_id: number | null;
  student_id: number | null;
  message: string;
  created_at: string;
}

export interface MonitoringStatus {
  active_connections: number;
  buffered_events: number;
  buffered_alerts: number;
  total_published: number;
  event_buffer_capacity: number;
  alert_buffer_capacity: number;
  max_connections: number;
}

export interface MonitoringConnectionStatus {
  active_connections: number;
  max_connections: number;
}

export interface MonitoringEventListResponse {
  items: MonitoringEvent[];
  count: number;
}

export interface MonitoringAlertListResponse {
  items: MonitoringAlert[];
  count: number;
}

// ---------------------------------------------------------------------------
// Sensitive field filtering
// ---------------------------------------------------------------------------

const SENSITIVE_KEYS = new Set([
  "face_image",
  "face_images",
  "face_embeddings",
  "biometric_data",
  "biometric_payload",
  "provider_credentials",
  "device_credentials",
  "api_key",
  "api_keys",
  "secret",
  "secrets",
  "password",
  "token",
  "raw_ocr",
  "ocr_payload",
  "database_url",
  "filesystem_path",
  "stack_trace",
  "traceback",
]);

export function safePayload(
  payload: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (!SENSITIVE_KEYS.has(k.toLowerCase())) {
      out[k] = v;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function getMonitoringStatus(): Promise<MonitoringStatus> {
  return request("/api/v1/monitoring/status");
}

export async function getMonitoringEvents(params: {
  limit?: number;
  category?: EventCategory;
  event_type?: EventType;
  min_severity?: EventSeverity;
  exam_id?: number;
  hall_id?: number;
}): Promise<MonitoringEventListResponse> {
  const sp = new URLSearchParams();
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.category) sp.set("category", params.category);
  if (params.event_type) sp.set("event_type", params.event_type);
  if (params.min_severity) sp.set("min_severity", params.min_severity);
  if (params.exam_id) sp.set("exam_id", String(params.exam_id));
  if (params.hall_id) sp.set("hall_id", String(params.hall_id));
  const qs = sp.toString();
  return request(`/api/v1/monitoring/events${qs ? `?${qs}` : ""}`);
}

export async function getMonitoringAlerts(params: {
  limit?: number;
  severity?: EventSeverity;
  event_type?: EventType;
  exam_id?: number;
  hall_id?: number;
}): Promise<MonitoringAlertListResponse> {
  const sp = new URLSearchParams();
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.severity) sp.set("severity", params.severity);
  if (params.event_type) sp.set("event_type", params.event_type);
  if (params.exam_id) sp.set("exam_id", String(params.exam_id));
  if (params.hall_id) sp.set("hall_id", String(params.hall_id));
  const qs = sp.toString();
  return request(`/api/v1/monitoring/alerts${qs ? `?${qs}` : ""}`);
}

export async function getMonitoringConnections(): Promise<MonitoringConnectionStatus> {
  return request("/api/v1/monitoring/connections");
}
