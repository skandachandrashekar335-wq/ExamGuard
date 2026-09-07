import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

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
  last_seen_at: string | null;
  last_health_check_at: string | null;
  health_reason: string | null;
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

export type CameraUpdate = Partial<CameraCreate> & { is_active?: boolean | null };

export function listCameras(params: {
  page?: number; page_size?: number; search?: string;
  exam_hall_id?: number; status?: string; include_inactive?: boolean;
} = {}): Promise<CameraListResponse> {
  return apiRequest(`/api/v1/cameras${qs(params)}`);
}

export function getCamera(id: number): Promise<Camera> {
  return apiRequest(`/api/v1/cameras/${id}`);
}

export function createCamera(data: CameraCreate): Promise<Camera> {
  return apiRequest("/api/v1/cameras", { method: "POST", body: JSON.stringify(data) });
}

export function updateCamera(id: number, data: CameraUpdate): Promise<Camera> {
  return apiRequest(`/api/v1/cameras/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deactivateCamera(id: number): Promise<Camera> {
  return apiRequest(`/api/v1/cameras/${id}`, { method: "DELETE" });
}

export interface EntryPoint {
  id: number; name: string; code: string; description: string | null;
  location_detail: string | null; exam_hall_id: number | null;
  is_active: boolean; created_at: string; updated_at: string;
}

export interface EntryPointListResponse {
  items: EntryPoint[]; page: number; page_size: number; total: number;
}

export interface EntryPointCreate {
  name: string; code: string; description?: string | null;
  location_detail?: string | null; exam_hall_id?: number | null;
}

export type EntryPointUpdate = Partial<EntryPointCreate> & { is_active?: boolean | null };

export function listEntryPoints(params: {
  page?: number; page_size?: number; search?: string;
  exam_hall_id?: number; include_inactive?: boolean;
} = {}): Promise<EntryPointListResponse> {
  return apiRequest(`/api/v1/entry-points${qs(params)}`);
}

export function getEntryPoint(id: number): Promise<EntryPoint> {
  return apiRequest(`/api/v1/entry-points/${id}`);
}

export function createEntryPoint(data: EntryPointCreate): Promise<EntryPoint> {
  return apiRequest("/api/v1/entry-points", { method: "POST", body: JSON.stringify(data) });
}

export function updateEntryPoint(id: number, data: EntryPointUpdate): Promise<EntryPoint> {
  return apiRequest(`/api/v1/entry-points/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deactivateEntryPoint(id: number): Promise<EntryPoint> {
  return apiRequest(`/api/v1/entry-points/${id}`, { method: "DELETE" });
}

export interface CameraEntryPointMapping {
  id: number; camera_id: number; entry_point_id: number;
  is_enabled: boolean; created_at: string; updated_at: string;
}

export interface MappingListResponse {
  items: CameraEntryPointMapping[]; page: number; page_size: number; total: number;
}

export interface MappingCreate { camera_id: number; entry_point_id: number; }

export function listMappings(params: {
  page?: number; page_size?: number; camera_id?: number;
  entry_point_id?: number; include_disabled?: boolean;
} = {}): Promise<MappingListResponse> {
  return apiRequest(`/api/v1/camera-entry-points${qs(params)}`);
}

export function createMapping(data: MappingCreate): Promise<CameraEntryPointMapping> {
  return apiRequest("/api/v1/camera-entry-points", { method: "POST", body: JSON.stringify(data) });
}

export function deactivateMapping(id: number): Promise<CameraEntryPointMapping> {
  return apiRequest(`/api/v1/camera-entry-points/${id}`, { method: "DELETE" });
}

export interface ExamHall {
  id: number; building: string; room_number: string;
  name: string | null; capacity: number; is_active: boolean;
}

export interface ExamHallListResponse {
  items: ExamHall[]; page: number; page_size: number; total: number;
}

export function listExamHalls(params: {
  page?: number; page_size?: number; include_inactive?: boolean;
} = {}): Promise<ExamHallListResponse> {
  return apiRequest(`/api/v1/exam-halls${qs(params)}`);
}

export interface CameraHealth {
  camera_id: number; status: string; last_seen_at: string | null;
  last_health_check_at: string | null; health_reason: string | null; is_active: boolean;
}

export interface HealthObservationCreate {
  status: string; observed_at?: string | null; reason?: string | null;
}

export function getCameraHealth(cameraId: number): Promise<CameraHealth> {
  return apiRequest(`/api/v1/cameras/${cameraId}/health`);
}

export function recordHealthObservation(
  cameraId: number, data: HealthObservationCreate
): Promise<CameraHealth> {
  return apiRequest(`/api/v1/cameras/${cameraId}/health-observations`, {
    method: "POST", body: JSON.stringify(data),
  });
}
