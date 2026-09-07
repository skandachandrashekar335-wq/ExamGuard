export interface AttendanceRecord {
  id: number;
  student_id: number;
  exam_id: number;
  exam_registration_id: number;
  status: string;
  entry_verification_id: number;
  entry_method: string;
  entry_time: string;
  hall_id: number;
  seat_number: string | null;
  recorded_at: string;
  updated_at: string;
}

export interface AttendanceEvent {
  id: number;
  student_id: number;
  exam_id: number;
  exam_registration_id: number;
  entry_verification_id: number;
  event_type: string;
  status_snapshot: string;
  recorded_by: string | null;
  reason: string | null;
  created_at: string;
}

export interface AttendanceListResponse {
  items: AttendanceRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface AttendanceEventListResponse {
  items: AttendanceEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface HallAttendanceSummary {
  hall_id: number;
  hall_name: string;
  total: number;
  present: number;
}

export interface AttendanceSummaryResponse {
  exam_id: number;
  total_registered: number;
  total_present: number;
  total_absent: number;
  total_excused: number;
  attendance_rate: number;
  by_hall: HallAttendanceSummary[];
}

export interface AttendanceCorrectionRequest {
  status: string;
  reason: string;
  recorded_by: string;
}

import { apiRequest, qs } from "./api";
export { ApiError } from "./api";

export async function listExamAttendance(
  examId: number,
  params: { hall_id?: number; status?: string; page?: number; page_size?: number } = {},
): Promise<AttendanceListResponse> {
  return apiRequest(`/api/v1/attendance/exams/${examId}${qs(params)}`);
}

export async function getAttendanceSummary(examId: number): Promise<AttendanceSummaryResponse> {
  return apiRequest(`/api/v1/attendance/exams/${examId}/summary`);
}

export async function getRegistrationAttendance(examRegistrationId: number): Promise<AttendanceRecord> {
  return apiRequest(`/api/v1/attendance/registrations/${examRegistrationId}`);
}

export async function correctAttendance(
  examRegistrationId: number,
  data: AttendanceCorrectionRequest,
): Promise<AttendanceRecord> {
  return apiRequest(`/api/v1/attendance/registrations/${examRegistrationId}/correct`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listStudentAttendance(
  studentId: number,
  params: { page?: number; page_size?: number } = {},
): Promise<AttendanceListResponse> {
  return apiRequest(`/api/v1/attendance/students/${studentId}${qs(params)}`);
}

export async function listEntryEvents(
  entryVerificationId: number,
  params: { page?: number; page_size?: number } = {},
): Promise<AttendanceEventListResponse> {
  return apiRequest(`/api/v1/attendance/events/${entryVerificationId}${qs(params)}`);
}
