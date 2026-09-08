"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";

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

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [subjects, setSubjects] = useState<SubjectOption[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editExam, setEditExam] = useState<Exam | null>(null);
  const [form, setForm] = useState({
    subject_id: "",
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

  useEffect(() => {
    fetchExams();
  }, [page, search, showInactive]);

  useEffect(() => {
    fetchSubjects();
  }, []);

  const resetForm = () => {
    setForm({
      subject_id: "",
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
      await apiRequest(url, { method, body: JSON.stringify(body) });
      setShowForm(false);
      resetForm();
      fetchExams();
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
                placeholder="Exam Name"
                value={form.exam_name}
                onChange={(e) =>
                  setForm({ ...form, exam_name: e.target.value })
                }
                className="eg-input"
              />
              <input
                type="date"
                value={form.exam_date}
                onChange={(e) =>
                  setForm({ ...form, exam_date: e.target.value })
                }
                className="eg-input"
              />
              <input
                type="time"
                placeholder="Start Time"
                value={form.start_time}
                onChange={(e) =>
                  setForm({ ...form, start_time: e.target.value })
                }
                className="eg-input"
              />
              <input
                type="time"
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
                placeholder="Department"
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
                className="eg-input"
              />
            </div>
            <div className="flex gap-4 mt-4">
              <button
                onClick={handleSubmit}
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
                  <td>{e.exam_name}</td>
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
                    <button
                      onClick={() => openEdit(e)}
                      className="eg-btn eg-btn-sm text-xs mr-4"
                    >
                      Edit
                    </button>
                    {e.is_active && (
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
