"use client";

import { useEffect, useState } from "react";

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

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (search) params.set("search", search);
    if (showInactive) params.set("include_inactive", "true");

    const res = await fetch(`${API}/api/v1/exams?${params}`);
    const data: ListResponse = await res.json();
    setExams(data.items);
    setTotal(data.total);
  };

  const fetchSubjects = async () => {
    const res = await fetch(`${API}/api/v1/subjects?page=1&page_size=100`);
    const data: SubjectListResponse = await res.json();
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
      ? `${API}/api/v1/exams/${editExam.id}`
      : `${API}/api/v1/exams`;
    const method = editExam ? "PATCH" : "POST";

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      setShowForm(false);
      resetForm();
      fetchExams();
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to save exam");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this exam?")) return;
    await fetch(`${API}/api/v1/exams/${id}`, { method: "DELETE" });
    fetchExams();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Exams
        </h1>
        <p className="text-[#999] mb-8">Manage examination schedules</p>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by exam name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="flex-1 bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-cyan-500"
          />
          <label className="flex items-center gap-2 text-sm text-[#999]">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="accent-cyan-500"
            />
            Show inactive
          </label>
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="bg-gradient-to-r from-cyan-500 to-pink-500 px-4 py-2 rounded-lg font-medium hover:opacity-90"
          >
            + Add Exam
          </button>
        </div>

        {showForm && (
          <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">
              {editExam ? "Edit Exam" : "New Exam"}
            </h2>
            {error && (
              <p className="text-pink-400 text-sm mb-4">{error}</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <select
                value={form.subject_id}
                onChange={(e) =>
                  setForm({ ...form, subject_id: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
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
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="date"
                value={form.exam_date}
                onChange={(e) =>
                  setForm({ ...form, exam_date: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="time"
                placeholder="Start Time"
                value={form.start_time}
                onChange={(e) =>
                  setForm({ ...form, start_time: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="time"
                placeholder="End Time"
                value={form.end_time}
                onChange={(e) =>
                  setForm({ ...form, end_time: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <select
                value={form.semester}
                onChange={(e) =>
                  setForm({ ...form, semester: Number(e.target.value) })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
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
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex gap-4 mt-4">
              <button
                onClick={handleSubmit}
                className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
              >
                {editExam ? "Update" : "Create"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
                className="border border-white/20 px-4 py-2 rounded-lg hover:bg-white/5"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                <th className="px-6 py-3">Exam Name</th>
                <th className="px-6 py-3">Subject</th>
                <th className="px-6 py-3">Date</th>
                <th className="px-6 py-3">Time</th>
                <th className="px-6 py-3">Dept</th>
                <th className="px-6 py-3">Sem</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {exams.map((e) => (
                <tr
                  key={e.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 text-sm">{e.exam_name}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {e.subject_code || "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {e.exam_date}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {e.start_time?.slice(0, 5)} — {e.end_time?.slice(0, 5)}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {e.department}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {e.semester}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        e.is_active
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {e.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() => openEdit(e)}
                      className="text-cyan-400 hover:text-cyan-300 text-sm mr-4"
                    >
                      Edit
                    </button>
                    {e.is_active && (
                      <button
                        onClick={() => handleDeactivate(e.id)}
                        className="text-pink-400 hover:text-pink-300 text-sm"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {exams.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-6 py-8 text-center text-[#666]"
                  >
                    No exams found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex justify-center gap-4 mt-6">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="border border-white/20 px-4 py-2 rounded-lg disabled:opacity-30 hover:bg-white/5"
            >
              Previous
            </button>
            <span className="py-2 text-sm text-[#999]">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="border border-white/20 px-4 py-2 rounded-lg disabled:opacity-30 hover:bg-white/5"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
