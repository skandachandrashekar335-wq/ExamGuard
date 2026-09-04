export interface IdentityVerificationAttempt {
  id: number;
  student_id: number;
  exam_registration_id: number;
  hall_ticket_id: number | null;
  status: string;
  verification_method: string;
  decision: string;
  failure_reason: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface IdentityVerificationEvidence {
  id: number;
  attempt_id: number;
  signal_type: string;
  signal_value: string | null;
  provider_name: string | null;
  provider_version: string | null;
  confidence: number | null;
  details: string | null;
  created_at: string;
}

export interface StudentInfo {
  id: number;
  usn: string;
  name: string;
}

export interface ExamInfo {
  id: number;
  subject_id: number;
  exam_name: string;
}

export interface VerificationContext {
  attempt: IdentityVerificationAttempt;
  evidence: IdentityVerificationEvidence[];
  student: StudentInfo | null;
  exam: ExamInfo | null;
}

export interface VerificationListResponse {
  items: IdentityVerificationAttempt[];
  total: number;
  page: number;
  page_size: number;
}

export interface VerifyFaceResponse {
  attempt_id: number;
  evidence: IdentityVerificationEvidence[];
}

export type VerificationStatus =
  | "CREATED"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type VerificationDecision =
  | "PENDING"
  | "MATCH"
  | "NO_MATCH"
  | "INCONCLUSIVE";

export const STATUS_LABELS: Record<string, string> = {
  CREATED: "Created",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export const DECISION_LABELS: Record<string, string> = {
  PENDING: "Pending",
  MATCH: "Match",
  NO_MATCH: "No Match",
  INCONCLUSIVE: "Inconclusive",
};
