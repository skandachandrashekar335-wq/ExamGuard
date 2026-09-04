const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || "Request failed");
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------

export interface Camera {
  id: number;
  name: string;
  device_identifier: string;
  camera_type: string | null;
  manufacturer: string | null;
  model_name: string | null;
  resolution_width: number | null;
  resolution_height: number | null;
  exam_hall_id: number | null;
  status: string;
  connection_info: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CameraListResponse {
  items: Camera[];
  page: number;
  page_size: number;
  total: number;
}

export interface CameraCreate {
  name: string;
  device_identifier: string;
  camera_type?: string | null;
  manufacturer?: string | null;
  model_name?: string | null;
  resolution_width?: number | null;
  resolution_height?: number | null;
  exam_hall_id?: number | null;
  connection_info?: string | null;
}

export type CameraUpdate = Partial<CameraCreate> & {
  status?: string | null;
  is_active?: boolean | null;
};

export function listCameras(params: {
  page?: number;
  page_size?: number;
  search?: string;
  exam_hall_id?: number;
  status?: string;
  include_inactive?: boolean;
} = {}): Promise<CameraListResponse> {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  if (params.search) q.set("search", params.search);
  if (params.exam_hall_id) q.set("exam_hall_id", String(params.exam_hall_id));
  if (params.status) q.set("status", params.status);
  if (params.include_inactive) q.set("include_inactive", "true");
  const qs = q.toString();
  return request(`/api/v1/cameras${qs ? `?${qs}` : ""}`);
}

export function getCamera(id: number): Promise<Camera> {
  return request(`/api/v1/cameras/${id}`);
}

export function createCamera(data: CameraCreate): Promise<Camera> {
  return request("/api/v1/cameras", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function updateCamera(id: number, data: CameraUpdate): Promise<Camera> {
  return request(`/api/v1/cameras/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deactivateCamera(id: number): Promise<Camera> {
  return request(`/api/v1/cameras/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Entry Point
// ---------------------------------------------------------------------------

export interface EntryPoint {
  id: number;
  name: string;
  code: string;
  description: string | null;
  location_detail: string | null;
  exam_hall_id: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EntryPointListResponse {
  items: EntryPoint[];
  page: number;
  page_size: number;
  total: number;
}

export interface EntryPointCreate {
  name: string;
  code: string;
  description?: string | null;
  location_detail?: string | null;
  exam_hall_id?: number | null;
}

export type EntryPointUpdate = Partial<EntryPointCreate> & {
  is_active?: boolean | null;
};

export function listEntryPoints(params: {
  page?: number;
  page_size?: number;
  search?: string;
  exam_hall_id?: number;
  include_inactive?: boolean;
} = {}): Promise<EntryPointListResponse> {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  if (params.search) q.set("search", params.search);
  if (params.exam_hall_id) q.set("exam_hall_id", String(params.exam_hall_id));
  if (params.include_inactive) q.set("include_inactive", "true");
  const qs = q.toString();
  return request(`/api/v1/entry-points${qs ? `?${qs}` : ""}`);
}

export function getEntryPoint(id: number): Promise<EntryPoint> {
  return request(`/api/v1/entry-points/${id}`);
}

export function createEntryPoint(data: EntryPointCreate): Promise<EntryPoint> {
  return request("/api/v1/entry-points", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function updateEntryPoint(id: number, data: EntryPointUpdate): Promise<EntryPoint> {
  return request(`/api/v1/entry-points/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deactivateEntryPoint(id: number): Promise<EntryPoint> {
  return request(`/api/v1/entry-points/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Camera ↔ Entry Point Mapping
// ---------------------------------------------------------------------------

export interface CameraEntryPointMapping {
  id: number;
  camera_id: number;
  entry_point_id: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface MappingListResponse {
  items: CameraEntryPointMapping[];
  page: number;
  page_size: number;
  total: number;
}

export interface MappingCreate {
  camera_id: number;
  entry_point_id: number;
}

export type MappingUpdate = {
  is_enabled?: boolean | null;
};

export function listMappings(params: {
  page?: number;
  page_size?: number;
  camera_id?: number;
  entry_point_id?: number;
  include_disabled?: boolean;
} = {}): Promise<MappingListResponse> {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  if (params.camera_id) q.set("camera_id", String(params.camera_id));
  if (params.entry_point_id) q.set("entry_point_id", String(params.entry_point_id));
  if (params.include_disabled) q.set("include_disabled", "true");
  const qs = q.toString();
  return request(`/api/v1/camera-entry-points${qs ? `?${qs}` : ""}`);
}

export function createMapping(data: MappingCreate): Promise<CameraEntryPointMapping> {
  return request("/api/v1/camera-entry-points", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deactivateMapping(id: number): Promise<CameraEntryPointMapping> {
  return request(`/api/v1/camera-entry-points/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Exam Hall (for selectors)
// ---------------------------------------------------------------------------

export interface ExamHall {
  id: number;
  building: string;
  room_number: string;
  name: string | null;
  capacity: number;
  is_active: boolean;
}

export interface ExamHallListResponse {
  items: ExamHall[];
  page: number;
  page_size: number;
  total: number;
}

export function listExamHalls(params: {
  page?: number;
  page_size?: number;
  include_inactive?: boolean;
} = {}): Promise<ExamHallListResponse> {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.page_size) q.set("page_size", String(params.page_size));
  if (params.include_inactive) q.set("include_inactive", "true");
  const qs = q.toString();
  return request(`/api/v1/exam-halls${qs ? `?${qs}` : ""}`);
}
