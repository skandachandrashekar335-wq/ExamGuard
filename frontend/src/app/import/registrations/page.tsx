"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_STUDENT_IDS = 500;

interface ExamOption {
  id: number;
  exam_name: string;
  exam_date: string;
  subject_code: string | null;
}

interface RegistrationResult {
  student_id: number;
  status: string;
  registration_id?: number;
  error?: string;
}

interface RegistrationResponse {
  total: number;
  created: number;
  skipped: number;
  failed: number;
  results: RegistrationResult[];
}

interface CancelResult {
  registration_id: number;
  status: string;
  error?: string;
}

interface CancelResponse {
  total: number;
  cancelled: number;
  skipped: number;
  failed: number;
  results: CancelResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

export default function ImportRegistrationsPage() {
  const [exams, setExams] = useState<ExamOption[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [phase, setPhase] = useState<Phase>("select");
  const [studentIds, setStudentIds] = useState<number[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<RegistrationResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/exams?page=1&page_size=100`)
      .then((r) => r.json())
      .then((data) => setExams(data.items || []))
      .catch(() => {});
  }, []);

  const reset = useCallback(() => {
    setPhase("select");
    setStudentIds([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback((file: File) => {
    setParseError("");

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string);

        if (!Array.isArray(data)) {
          setParseError("JSON must be an array of student IDs");
          return;
        }

        if (data.length === 0) {
          setParseError("File contains no student IDs");
          return;
        }

        if (data.length > MAX_STUDENT_IDS) {
          setParseError(
            `File contains ${data.length} IDs, maximum is ${MAX_STUDENT_IDS}`
          );
          return;
        }

        if (data.some((id: unknown) => typeof id !== "number" || id <= 0 || !Number.isInteger(id))) {
          setParseError("All student IDs must be positive integers");
          return;
        }

        setStudentIds(data as number[]);
        setPhase("preview");
      } catch {
        setParseError("Invalid JSON file");
      }
    };
    reader.readAsText(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleSubmit = async () => {
    if (!selectedExamId) return;
    setPhase("submitting");
    setSubmitError("");

    try {
      const res = await fetch(`${API}/api/v1/import/registrations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exam_id: selectedExamId,
          student_ids: studentIds,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data: RegistrationResponse = await res.json();
      setResponse(data);
      setPhase("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Import failed");
      setPhase("preview");
    }
  };

  const selectedExam = exams.find((e) => e.id === selectedExamId);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import Registrations
        </h1>
        <p className="text-[#999] mb-8">
          Bulk register students for an exam (max {MAX_STUDENT_IDS} per batch)
        </p>

        {phase === "select" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Select Exam</h2>
              <select
                value={selectedExamId ?? ""}
                onChange={(e) =>
                  setSelectedExamId(
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="w-full bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              >
                <option value="">Choose an exam...</option>
                {exams.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.exam_name} — {e.exam_date}
                    {e.subject_code ? ` (${e.subject_code})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {selectedExamId && (
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-white/20 rounded-lg p-16 text-center hover:border-white/40 transition-colors cursor-pointer"
                onClick={() => fileRef.current?.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".json"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFile(file);
                  }}
                />
                <p className="text-[#999] text-lg mb-2">
                  Drop a JSON file with student IDs or click to select
                </p>
                <p className="text-[#666] text-sm">
                  Format: [1, 2, 3, ...] (array of student IDs)
                </p>
              </div>
            )}
          </div>
        )}

        {parseError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mb-6">
            <p className="text-pink-400 text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && selectedExam && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#999]">
                    Exam:{" "}
                    <span className="text-white">
                      {selectedExam.exam_name}
                    </span>{" "}
                    ({selectedExam.exam_date})
                  </p>
                  <p className="text-sm text-[#999]">
                    <span className="text-white font-medium">
                      {studentIds.length}
                    </span>{" "}
                    student ID{studentIds.length !== 1 ? "s" : ""} ready
                  </p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={reset}
                    className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSubmit}
                    className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
                  >
                    Register {studentIds.length} Student{studentIds.length !== 1 ? "s" : ""}
                  </button>
                </div>
              </div>
            </div>

            <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                    <th className="px-6 py-3">#</th>
                    <th className="px-6 py-3">Student ID</th>
                  </tr>
                </thead>
                <tbody>
                  {studentIds.map((id, i) => (
                    <tr
                      key={i}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-6 py-3 text-sm text-[#666]">{i + 1}</td>
                      <td className="px-6 py-3 font-mono text-sm">{id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {phase === "submitting" && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-[#999]">Registering students...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="grid grid-cols-4 gap-4 mb-6">
              {[
                { label: "Total", value: response.total, color: "text-white" },
                { label: "Created", value: response.created, color: "text-emerald-400" },
                { label: "Skipped", value: response.skipped, color: "text-amber-400" },
                { label: "Failed", value: response.failed, color: "text-pink-400" },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="bg-[#111] border border-white/10 rounded-lg p-4 text-center"
                >
                  <p className={`text-2xl font-bold ${stat.color}`}>
                    {stat.value}
                  </p>
                  <p className="text-[#999] text-sm">{stat.label}</p>
                </div>
              ))}
            </div>

            {response.results.length > 0 && (
              <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                      <th className="px-6 py-3">Student ID</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Registration ID</th>
                      <th className="px-6 py-3">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.results.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-3 font-mono text-sm">
                          {r.student_id}
                        </td>
                        <td className="px-6 py-3">
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              r.status === "created"
                                ? "bg-emerald-500/20 text-emerald-400"
                                : r.status === "skipped"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-pink-500/20 text-pink-400"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="px-6 py-3 text-sm text-[#999]">
                          {r.registration_id ?? "—"}
                        </td>
                        <td className="px-6 py-3 text-sm text-[#999]">
                          {r.error || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <button
              onClick={reset}
              className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
            >
              Import Another Batch
            </button>
          </div>
        )}

        {submitError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mt-4">
            <p className="text-pink-400 text-sm">{submitError}</p>
          </div>
        )}

        <div className="mt-8">
          <Link
            href="/import"
            className="text-[#666] hover:text-white text-sm transition-colors"
          >
            &larr; Back to Import
          </Link>
        </div>
      </div>
    </div>
  );
}
