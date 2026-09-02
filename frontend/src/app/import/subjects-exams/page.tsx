"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_SUBJECTS = 200;
const MAX_EXAMS = 500;

interface SubjectItem {
  code: string;
  name: string;
  department: string;
  semester: number;
  credits?: number;
}

interface ExamItem {
  subject_code: string;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  semester: number;
  department: string;
}

interface SubjectResult {
  code: string;
  department: string;
  status: string;
  error?: string;
}

interface ExamResult {
  subject_code: string;
  exam_name: string;
  status: string;
  error?: string;
}

interface ImportResponse {
  subject_total: number;
  subject_created: number;
  subject_skipped: number;
  subject_failed: number;
  exam_total: number;
  exam_created: number;
  exam_skipped: number;
  exam_failed: number;
  subject_results: SubjectResult[];
  exam_results: ExamResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

interface ParsedData {
  subjects: SubjectItem[];
  exams: ExamItem[];
}

export default function ImportSubjectsExamsPage() {
  const [phase, setPhase] = useState<Phase>("select");
  const [parsed, setParsed] = useState<ParsedData>({ subjects: [], exams: [] });
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<ImportResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setPhase("select");
    setParsed({ subjects: [], exams: [] });
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

        if (!data || typeof data !== "object") {
          setParseError("JSON must be an object with 'subjects' and/or 'exams' arrays");
          return;
        }

        const subjects: SubjectItem[] = Array.isArray(data.subjects)
          ? data.subjects
          : [];
        const exams: ExamItem[] = Array.isArray(data.exams) ? data.exams : [];

        if (subjects.length === 0 && exams.length === 0) {
          setParseError("Provide at least one of 'subjects' or 'exams' arrays");
          return;
        }

        if (subjects.length > MAX_SUBJECTS) {
          setParseError(
            `Too many subjects: ${subjects.length} (max ${MAX_SUBJECTS})`
          );
          return;
        }

        if (exams.length > MAX_EXAMS) {
          setParseError(
            `Too many exams: ${exams.length} (max ${MAX_EXAMS})`
          );
          return;
        }

        for (const s of subjects) {
          if (!s.code || !s.name || !s.department || !s.semester) {
            setParseError(
              "Each subject must have 'code', 'name', 'department', and 'semester'"
            );
            return;
          }
        }

        for (const e of exams) {
          if (
            !e.subject_code ||
            !e.exam_name ||
            !e.exam_date ||
            !e.start_time ||
            !e.end_time ||
            !e.semester ||
            !e.department
          ) {
            setParseError(
              "Each exam must have 'subject_code', 'exam_name', 'exam_date', 'start_time', 'end_time', 'semester', and 'department'"
            );
            return;
          }
        }

        setParsed({ subjects, exams });
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
    setPhase("submitting");
    setSubmitError("");

    try {
      const body: Record<string, unknown> = {};
      if (parsed.subjects.length > 0) body.subjects = parsed.subjects;
      if (parsed.exams.length > 0) body.exams = parsed.exams;

      const res = await fetch(`${API}/api/v1/import/subjects-exams`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data: ImportResponse = await res.json();
      setResponse(data);
      setPhase("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Import failed");
      setPhase("preview");
    }
  };

  const totalItems = parsed.subjects.length + parsed.exams.length;

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import Subjects &amp; Exams
        </h1>
        <p className="text-[#999] mb-8">
          Bulk import subjects (max {MAX_SUBJECTS}) and exams (max {MAX_EXAMS})
          from a JSON file
        </p>

        {phase === "select" && (
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
              Drop a JSON file here or click to select
            </p>
            <p className="text-[#666] text-sm">
              Format: {"{"} "subjects": [...], "exams": [...] {"}"}
            </p>
          </div>
        )}

        {parseError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mb-6">
            <p className="text-pink-400 text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4 mb-6 flex items-center justify-between">
              <p className="text-sm text-[#999]">
                <span className="text-white font-medium">{totalItems}</span>{" "}
                item{totalItems !== 1 ? "s" : ""} ready to import (
                {parsed.subjects.length} subject
                {parsed.subjects.length !== 1 ? "s" : ""},{" "}
                {parsed.exams.length} exam
                {parsed.exams.length !== 1 ? "s" : ""})
              </p>
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
                  Import All
                </button>
              </div>
            </div>

            {parsed.subjects.length > 0 && (
              <div className="mb-6">
                <h2 className="text-lg font-semibold mb-3">
                  Subjects ({parsed.subjects.length})
                </h2>
                <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                        <th className="px-6 py-3">#</th>
                        <th className="px-6 py-3">Code</th>
                        <th className="px-6 py-3">Name</th>
                        <th className="px-6 py-3">Department</th>
                        <th className="px-6 py-3">Sem</th>
                      </tr>
                    </thead>
                    <tbody>
                      {parsed.subjects.map((s, i) => (
                        <tr
                          key={i}
                          className="border-b border-white/5 hover:bg-white/[0.02]"
                        >
                          <td className="px-6 py-3 text-sm text-[#666]">
                            {i + 1}
                          </td>
                          <td className="px-6 py-3 font-mono text-sm">{s.code}</td>
                          <td className="px-6 py-3 text-sm">{s.name}</td>
                          <td className="px-6 py-3 text-sm text-[#999]">
                            {s.department}
                          </td>
                          <td className="px-6 py-3 text-sm text-[#999]">
                            {s.semester}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {parsed.exams.length > 0 && (
              <div className="mb-6">
                <h2 className="text-lg font-semibold mb-3">
                  Exams ({parsed.exams.length})
                </h2>
                <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                        <th className="px-6 py-3">#</th>
                        <th className="px-6 py-3">Subject</th>
                        <th className="px-6 py-3">Exam Name</th>
                        <th className="px-6 py-3">Date</th>
                        <th className="px-6 py-3">Time</th>
                        <th className="px-6 py-3">Dept</th>
                      </tr>
                    </thead>
                    <tbody>
                      {parsed.exams.map((e, i) => (
                        <tr
                          key={i}
                          className="border-b border-white/5 hover:bg-white/[0.02]"
                        >
                          <td className="px-6 py-3 text-sm text-[#666]">
                            {i + 1}
                          </td>
                          <td className="px-6 py-3 font-mono text-sm">
                            {e.subject_code}
                          </td>
                          <td className="px-6 py-3 text-sm">{e.exam_name}</td>
                          <td className="px-6 py-3 text-sm text-[#999]">
                            {e.exam_date}
                          </td>
                          <td className="px-6 py-3 text-sm text-[#999]">
                            {e.start_time} — {e.end_time}
                          </td>
                          <td className="px-6 py-3 text-sm text-[#999]">
                            {e.department}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {phase === "submitting" && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-[#999]">Importing subjects and exams...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-3">Subjects</h2>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "Total", value: response.subject_total, color: "text-white" },
                  { label: "Created", value: response.subject_created, color: "text-emerald-400" },
                  { label: "Skipped", value: response.subject_skipped, color: "text-amber-400" },
                  { label: "Failed", value: response.subject_failed, color: "text-pink-400" },
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
            </div>

            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-3">Exams</h2>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "Total", value: response.exam_total, color: "text-white" },
                  { label: "Created", value: response.exam_created, color: "text-emerald-400" },
                  { label: "Skipped", value: response.exam_skipped, color: "text-amber-400" },
                  { label: "Failed", value: response.exam_failed, color: "text-pink-400" },
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
            </div>

            {response.subject_results.length > 0 && (
              <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                      <th className="px-6 py-3">Code</th>
                      <th className="px-6 py-3">Department</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.subject_results.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-3 font-mono text-sm">{r.code}</td>
                        <td className="px-6 py-3 text-sm text-[#999]">
                          {r.department}
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
                          {r.error || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {response.exam_results.length > 0 && (
              <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                      <th className="px-6 py-3">Subject</th>
                      <th className="px-6 py-3">Exam Name</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.exam_results.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-3 font-mono text-sm">
                          {r.subject_code}
                        </td>
                        <td className="px-6 py-3 text-sm">{r.exam_name}</td>
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
