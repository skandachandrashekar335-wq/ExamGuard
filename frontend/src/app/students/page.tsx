"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";

interface Student {
  id: number;
  usn: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: Student[];
  page: number;
  page_size: number;
  total: number;
}

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editStudent, setEditStudent] = useState<Student | null>(null);
  const [formUsn, setFormUsn] = useState("");
  const [formName, setFormName] = useState("");
  const [error, setError] = useState("");

  const fetchStudents = async () => {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (search) params.search = search;
    if (showInactive) params.include_inactive = "true";

    const data = await apiRequest<ListResponse>(`/api/v1/students${qs(params)}`);
    setStudents(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchStudents();
  }, [page, search, showInactive]);

  const handleCreate = async () => {
    setError("");
    try {
      await apiRequest("/api/v1/students", {
        method: "POST",
        body: JSON.stringify({ usn: formUsn, name: formName }),
      });
      setShowForm(false);
      setFormUsn("");
      setFormName("");
      fetchStudents();
    } catch (err: any) {
      setError(err.message || "Failed to create student");
    }
  };

  const handleUpdate = async () => {
    if (!editStudent) return;
    setError("");
    try {
      await apiRequest(`/api/v1/students/${editStudent.id}`, {
        method: "PATCH",
        body: JSON.stringify({ usn: formUsn, name: formName }),
      });
      setEditStudent(null);
      setFormUsn("");
      setFormName("");
      fetchStudents();
    } catch (err: any) {
      setError(err.message || "Failed to update student");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this student?")) return;
    await apiRequest(`/api/v1/students/${id}`, { method: "DELETE" });
    fetchStudents();
  };

  const openEdit = (s: Student) => {
    setEditStudent(s);
    setFormUsn(s.usn);
    setFormName(s.name);
    setShowForm(true);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <p className="eg-breadcrumb">HOME / STUDENTS</p>
          <h1 className="eg-page-title">Students</h1>
          <p className="eg-page-desc">Manage student records</p>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search by USN or name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="eg-input flex-1"
          />
          <label className="eg-label flex items-center gap-2">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="eg-checkbox"
            />
            Show inactive
          </label>
          <button
            onClick={() => {
              setEditStudent(null);
              setFormUsn("");
              setFormName("");
              setShowForm(true);
            }}
            className="eg-btn eg-btn-primary"
          >
            + Add Student
          </button>
        </div>

        {showForm && (
          <div className="glass-surface glass p-6 mb-6">
            <h2 className="eg-page-title text-lg mb-4">
              {editStudent ? "Edit Student" : "New Student"}
            </h2>
            {error && (
              <p className="text-sm mb-4" style={{ color: "var(--danger)" }}>{error}</p>
            )}
            <div className="flex gap-4">
              <input
                type="text"
                placeholder="USN"
                value={formUsn}
                onChange={(e) => setFormUsn(e.target.value)}
                className="eg-input flex-1"
              />
              <input
                type="text"
                placeholder="Name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="eg-input flex-1"
              />
              <button
                onClick={editStudent ? handleUpdate : handleCreate}
                className="eg-btn eg-btn-primary"
              >
                {editStudent ? "Update" : "Create"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditStudent(null);
                  setError("");
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
                <th>USN</th>
                <th>Name</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>{s.usn}</td>
                  <td>{s.name}</td>
                  <td>
                    <span
                      className={`eg-badge ${s.is_active ? "eg-badge-success" : "eg-badge-danger"}`}
                    >
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="text-right">
                    <button
                      onClick={() => openEdit(s)}
                      className="eg-btn text-xs mr-4"
                    >
                      Edit
                    </button>
                    {s.is_active && (
                      <button
                        onClick={() => handleDeactivate(s.id)}
                        className="eg-btn eg-btn-danger text-xs"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr>
                  <td colSpan={4}>
                    <div className="eg-empty">
                      <p className="eg-empty-title">No students found</p>
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
              className="eg-btn eg-btn-sm"
            >
              Previous
            </button>
            <span className="eg-mono-sm" style={{ color: "var(--text-muted)" }}>
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn eg-btn-sm"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
