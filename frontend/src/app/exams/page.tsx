"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { createSession, type ExaminationSession } from "@/lib/session-api";

interface Exam {
  id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  semester: number;
  department: string;
  is_active: boolean;
  subject_code: string | null;
  subject_name: string | null;
  created_at: string;
  updated_at: string;
}

interface SubjectOption {
  id: number;
  code: string;
  name: string;
}

interface ListResponse {
  items: Exam[];
  page: number;
  page_size: number;
  total: number;
}

interface SubjectListResponse {
  items: SubjectOption[];
  total: number;
}

interface HallOption {
  id: number;
  building: string;
  room_number: string;
  name: string | null;
  capacity: number;
  is_active: boolean;
}

interface AssignmentStatus {
  id: number;
  is_active: boolean;
  user_email: string | null;
  user_name: string | null;
  exam_hall_id: number;
}

interface ExamPreparation {
  sessions: ExaminationSession[];
  readiness: {
    candidates_enrolled: number;
    reference_photos_enrolled: number;
    candidates_needing_review: number;
  };
  assignments: AssignmentStatus[];
}

export default function ExamsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "ADMIN" || user?.role === "OPERATOR";
  const [exams, setExams] = useState<Exam[]>([]);
  const [subjects, setSubjects] = useState<SubjectOption[]>([]);
  const [halls, setHalls] = useState<HallOption[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editExam, setEditExam] = useState<Exam | null>(null);
  const [selectedDetails, setSelectedDetails] = useState<Exam | null>(null);
  const [preparation, setPreparation] = useState<ExamPreparation | null>(null);
  const [preparationLoading, setPreparationLoading] = useState(false);
  const [preparationMessage, setPreparationMessage] = useState("");
  const [preparationError, setPreparationError] = useState("");
  const [preparationHallId, setPreparationHallId] = useState("");
  const [form, setForm] = useState({
    subject_id: "",
    hall_id: "",
    exam_name: "",
    exam_date: "",
    start_time: "",
    end_time: "",
    semester: 1,
    department: "",
  });
  const [error, setError] = useState("");

  const fetchExams = async () => {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (search) params.search = search;
    if (showInactive) params.include_inactive = "true";

    const data = await apiRequest<ListResponse>(`/api/v1/exams${qs(params)}`);
    setExams(data.items);
    setTotal(data.total);
  };

  const fetchSubjects = async () => {
    const data = await apiRequest<SubjectListResponse>(`/api/v1/subjects${qs({ page: 1, page_size: 100 })}`);
    setSubjects(data.items || []);
  };

  const fetchHalls = async () => {
    const data = await apiRequest<{ items: HallOption[] }>(
      `/api/v1/exam-halls${qs({ page: 1, page_size: 100 })}`
    );
    setHalls(data.items.filter((hall) => hall.is_active));
  };

  const openDetails = async (exam: Exam, message = "") => {
    setSelectedDetails(exam);
    setPreparation(null);
    setPreparationMessage(message);
    setPreparationError("");
    setPreparationLoading(true);
    try {
      const [sessionData, readiness, assignmentData] = await Promise.all([
        apiRequest<{ items: ExaminationSession[] }>(
          `/api/v1/examination-sessions${qs({ exam_id: exam.id, page_size: 100 })}`
        ),
        apiRequest<ExamPreparation["readiness"]>(
          `/api/v1/exams/${exam.id}/enrollment-readiness`
        ),
        apiRequest<{ items: AssignmentStatus[] }>(
          `/api/v1/invigilator-assignments${qs({ exam_id: exam.id, page_size: 100 })}`
        ),
      ]);
      setPreparation({
        sessions: sessionData.items,
        readiness,
        assignments: assignmentData.items,
      });
      setPreparationHallId("");
    } catch (err) {
      setPreparationError(
        err instanceof Error ? err.message : "Failed to load exam preparation details"
      );
    } finally {
      setPreparationLoading(false);
    }
  };

  const handleAddSession = async () => {
    if (!selectedDetails || !preparationHallId) return;
    const hallId = Number(preparationHallId);
    const hall = halls.find((item) => item.id === hallId);
    try {
      await createSession({
        exam_id: selectedDetails.id,
        exam_hall_id: hallId,
        expected_capacity: hall?.capacity,
        created_by: user?.email || undefined,
      });
      await openDetails(selectedDetails, "Hall session prepared in NOT_STARTED state.");
    } catch (err) {
      setPreparationError(
        err instanceof Error ? err.message : "Failed to prepare hall session"
      );
    }
  };

  useEffect(() => {
    fetchExams();
  }, [page, search, showInactive]);

  useEffect(() => {
    fetchSubjects();
    fetchHalls();
  }, []);

  const resetForm = () => {
    setForm({
      subject_id: "",
      hall_id: "",
      exam_name: "",
      exam_date: "",
      start_time: "",
      end_time: "",
      semester: 1,
      department: "",
    });
    setEditExam(null);
    setError("");
  };

  const openEdit = (e: Exam) => {
    setEditExam(e);
    setForm({
      subject_id: e.subject_id.toString(),
      hall_id: "",
      exam_name: e.exam_name,
      exam_date: e.exam_date,
      start_time: e.start_time.slice(0, 5),
      end_time: e.end_time.slice(0, 5),
      semester: e.semester,
      department: e.department,
    });
    setShowForm(true);
  };

  const handleSubmit = async () => {
    setError("");
    if (!form.subject_id || !form.exam_name.trim() || !form.exam_date ||
      !form.start_time || !form.end_time || !form.department.trim() ||
      (!editExam && !form.hall_id)) {
      setError("Complete all required exam fields and select a hall.");
      return;
    }
    const body = {
      subject_id: Number(form.subject_id),
      exam_name: form.exam_name,
      exam_date: form.exam_date,
      start_time: form.start_time,
      end_time: form.end_time,
      semester: Number(form.semester),
      department: form.department,
    };

    const url = editExam
      ? `/api/v1/exams/${editExam.id}`
      : "/api/v1/exams";
    const method = editExam ? "PATCH" : "POST";

    try {
      const saved = await apiRequest<Exam>(url, {
        method,
        body: JSON.stringify(body),
      });
      let sessionError = "";
      if (!editExam) {
        try {
          const hall = halls.find((item) => item.id === Number(form.hall_id));
          await createSession({
            exam_id: saved.id,
            exam_hall_id: Number(form.hall_id),
            expected_capacity: hall?.capacity,
            created_by: user?.email || undefined,
          });
        } catch (sessionErr) {
          sessionError = sessionErr instanceof Error
            ? `Exam saved, but hall/session preparation failed: ${sessionErr.message}`
            : "Exam saved, but hall/session preparation failed.";
        }
      }
      setShowForm(false);
      resetForm();
      await fetchExams();
      if (selectedDetails?.id === saved.id || !editExam) {
        await openDetails(saved, sessionError);
      }
    } catch (err: any) {
      setError(err.message || "Failed to save exam");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this exam?")) return;
    await apiRequest(`/api/v1/exams/${id}`, { method: "DELETE" });
    fetchExams();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <div>
            <h1 className="eg-page-title">Exams</h1>
            <p className="eg-page-desc">Manage examination schedules</p>
          </div>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search by exam name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="eg-input flex-1"
          />
          <label className="eg-label">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="accent-[var(--accent)]"
            />
            Show inactive
          </label>
          <button
            disabled={!canManage}
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="eg-btn eg-btn-primary"
          >
            + Add Exam
          </button>
        </div>

        {showForm && (
          <div className="glass-surface p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
              {editExam ? "Edit Exam" : "New Exam"}
            </h2>
            {error && (
              <p className="text-sm mb-4" style={{ color: "var(--danger)" }}>{error}</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <select
                required
                value={form.subject_id}
                onChange={(e) =>
                  setForm({ ...form, subject_id: e.target.value })
                }
                className="eg-select"
              >
                <option value="">Select Subject</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
              <input
                type="text"
                required
                placeholder="Exam Name"
                value={form.exam_name}
                onChange={(e) =>
                  setForm({ ...form, exam_name: e.target.value })
                }
                className="eg-input"
              />
              <input
                type="date"
                required
                value={form.exam_date}
                onChange={(e) =>
                  setForm({ ...form, exam_date: e.target.value })
                }
                className="eg-input"
              />
              <input
                type="time"
                required
                placeholder="Start Time"
                value={form.start_time}
                onChange={(e) =>
                  setForm({ ...form, start_time: e.target.value })
                }
                className="eg-input"
              />
              <input
                type="time"
                required
                placeholder="End Time"
                value={form.end_time}
                onChange={(e) =>
                  setForm({ ...form, end_time: e.target.value })
                }
                className="eg-input"
              />
              <select
                value={form.semester}
                onChange={(e) =>
                  setForm({ ...form, semester: Number(e.target.value) })
                }
                className="eg-select"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                  <option key={s} value={s}>
                    Semester {s}
                  </option>
                ))}
              </select>
              <input
                type="text"
                required
                placeholder="Department"
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
                className="eg-input"
              />
              {!editExam && (
                <select
                  required
                  value={form.hall_id}
                  onChange={(e) => setForm({ ...form, hall_id: e.target.value })}
                  className="eg-select"
                >
                  <option value="">Select exam hall</option>
                  {halls.map((hall) => (
                    <option key={hall.id} value={hall.id}>
                      {hall.name || `${hall.building} ${hall.room_number}`} · Capacity {hall.capacity}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="flex gap-4 mt-4">
              <button
                onClick={handleSubmit}
                disabled={!canManage || (!editExam && halls.length === 0)}
                className="eg-btn eg-btn-primary"
              >
                {editExam ? "Update" : "Create"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
                className="eg-btn"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {selectedDetails && (
          <section className="glass-surface p-5 mb-6" aria-label="Exam preparation details">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                  {selectedDetails.exam_name}
                </h2>
                <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {selectedDetails.exam_date} · {selectedDetails.start_time.slice(0, 5)}–{selectedDetails.end_time.slice(0, 5)}
                  {selectedDetails.subject_name ? ` · ${selectedDetails.subject_name}` : ""}
                  {` · Semester ${selectedDetails.semester} · ${selectedDetails.department}`}
                </p>
              </div>
              <button
                type="button"
                className="eg-btn eg-btn-sm"
                aria-label="Close exam details"
                onClick={() => {
                  setSelectedDetails(null);
                  setPreparation(null);
                }}
              >
                Close
              </button>
            </div>

            {preparationLoading ? (
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading preparation status...</p>
            ) : preparationError ? (
              <p className="text-sm" style={{ color: "var(--danger)" }}>{preparationError}</p>
            ) : preparation && (
              <>
                {preparationMessage && (
                  <p className="text-sm mb-3" style={{ color: "var(--success)" }}>{preparationMessage}</p>
                )}
                <div className="eg-grid-3 mb-4">
                  <div className="eg-metric">
                    <div className="eg-metric-label">Preparation</div>
                    <div className="eg-metric-value" style={{ fontSize: "1rem" }}>
                      {preparation.sessions.length ? "HALL PREPARED" : "HALL REQUIRED"}
                    </div>
                  </div>
                  <div className="eg-metric">
                    <div className="eg-metric-label">Registered Candidates</div>
                    <div className="eg-metric-value">{preparation.readiness.candidates_enrolled}</div>
                  </div>
                  <div className="eg-metric">
                    <div className="eg-metric-label">Reference Photos Enrolled</div>
                    <div className="eg-metric-value">{preparation.readiness.reference_photos_enrolled}</div>
                  </div>
                  <div className="eg-metric">
                    <div className="eg-metric-label">Candidates Needing Review</div>
                    <div className="eg-metric-value">{preparation.readiness.candidates_needing_review}</div>
                  </div>
                </div>

                <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
                  Invigilator assignment: {preparation.assignments.length ? "ASSIGNED" : "NOT ASSIGNED"}
                </p>

                {preparation.sessions.length > 0 && (
                  <div className="eg-table-wrap mb-4">
                    <table className="eg-table">
                      <thead>
                        <tr><th>Hall</th><th>Capacity</th><th>Session</th><th>Gate</th></tr>
                      </thead>
                      <tbody>
                        {preparation.sessions.map((session) => {
                          const hall = halls.find((item) => item.id === session.exam_hall_id);
                          return (
                            <tr key={session.id}>
                              <td>{hall?.name || (hall ? `${hall.building} ${hall.room_number}` : `Hall #${session.exam_hall_id}`)}</td>
                              <td>{session.expected_capacity ?? hall?.capacity ?? "—"}</td>
                              <td><span className="eg-badge eg-badge-info">{session.status}</span></td>
                              <td>{session.gate_status}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {preparation.assignments.length > 0 && (
                  <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
                    Assigned invigilators: {preparation.assignments.map((item) => item.user_email || item.user_name || `User #${item.id}`).join(", ")}
                  </p>
                )}

                {canManage && halls.some((hall) =>
                  !preparation.sessions.some((session) => session.exam_hall_id === hall.id)
                ) && (
                  <div className="flex flex-wrap items-end gap-3">
                    <label className="eg-label">
                      Add hall session
                      <select
                        value={preparationHallId}
                        onChange={(e) => setPreparationHallId(e.target.value)}
                        className="eg-select block mt-1"
                      >
                        <option value="">Select exam hall</option>
                        {halls.filter((hall) =>
                          !preparation.sessions.some((session) => session.exam_hall_id === hall.id)
                        ).map((hall) => (
                          <option key={hall.id} value={hall.id}>
                            {hall.name || `${hall.building} ${hall.room_number}`}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="eg-btn eg-btn-primary"
                      disabled={!preparationHallId}
                      onClick={handleAddSession}
                    >
                      Prepare Session
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        <div className="eg-table-wrap">
          <table className="eg-table">
            <thead>
              <tr>
                <th>Exam Name</th>
                <th>Subject</th>
                <th>Date</th>
                <th>Time</th>
                <th>Dept</th>
                <th>Sem</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {exams.map((e) => (
                <tr key={e.id}>
                  <td>
                    {canManage ? (
                      <button
                        type="button"
                        className="text-left font-medium hover:underline"
                        onClick={() => void openDetails(e)}
                      >
                        {e.exam_name}
                      </button>
                    ) : e.exam_name}
                  </td>
                  <td>{e.subject_code || "—"}</td>
                  <td>{e.exam_date}</td>
                  <td>
                    {e.start_time?.slice(0, 5)} — {e.end_time?.slice(0, 5)}
                  </td>
                  <td>{e.department}</td>
                  <td>{e.semester}</td>
                  <td>
                    <span className={`eg-badge ${e.is_active ? "eg-badge-success" : "eg-badge-danger"}`}>
                      {e.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="text-right">
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => void openDetails(e)}
                        className="eg-btn eg-btn-sm text-xs mr-2"
                      >
                        Details
                      </button>
                    )}
                    {canManage && (
                      <button
                        onClick={() => openEdit(e)}
                        className="eg-btn eg-btn-sm text-xs mr-2"
                      >
                        Edit
                      </button>
                    )}
                    {canManage && e.is_active && (
                      <button
                        onClick={() => handleDeactivate(e.id)}
                        className="eg-btn eg-btn-danger eg-btn-sm text-xs"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {exams.length === 0 && (
                <tr>
                  <td colSpan={8}>
                    <div className="eg-empty">
                      <p className="eg-empty-title">No exams found</p>
                      <p className="eg-empty-desc">Try adjusting your search or filters</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="eg-pagination">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="eg-btn"
            >
              Previous
            </button>
            <span className="eg-pagination-info">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
