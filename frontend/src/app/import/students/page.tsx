"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_STUDENTS = 500;

interface StudentItem {
  usn: string;
  name: string;
}

interface ImportResult {
  usn: string;
  status: string;
  error?: string;
}

interface ImportResponse {
  total: number;
  created: number;
  skipped: number;
  failed: number;
  results: ImportResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

export default function ImportStudentsPage() {
  const [phase, setPhase] = useState<Phase>("select");
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<ImportResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setPhase("select");
    setStudents([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback((file: File) => {
    setParseError("");
    setStudents([]);

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result as string);

        if (!Array.isArray(data)) {
          setParseError("JSON must be an array of student objects");
          return;
        }

        if (data.length === 0) {
          setParseError("File contains no students");
          return;
        }

        if (data.length > MAX_STUDENTS) {
          setParseError(
            `File contains ${data.length} students, maximum is ${MAX_STUDENTS}`
          );
          return;
        }

        const invalid = data.find(
          (item: Record<string, unknown>) =>
            !item.usn || typeof item.usn !== "string" || !item.name || typeof item.name !== "string"
        );
        if (invalid) {
          setParseError(
            "Each student must have a non-empty 'usn' and 'name' string"
          );
          return;
        }

        setStudents(data as StudentItem[]);
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
      const res = await fetch(`${API}/api/v1/import/students`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ students }),
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

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import Students
        </h1>
        <p className="text-[#999] mb-8">
          Bulk import student records from a JSON file (max {MAX_STUDENTS})
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
              Expected format: [{"{"} "usn": "...", "name": "..." {"}"}]
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
                <span className="text-white font-medium">{students.length}</span>{" "}
                student{students.length !== 1 ? "s" : ""} ready to import
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
                  Import {students.length} Student{students.length !== 1 ? "s" : ""}
                </button>
              </div>
            </div>

            <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                    <th className="px-6 py-3">#</th>
                    <th className="px-6 py-3">USN</th>
                    <th className="px-6 py-3">Name</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s, i) => (
                    <tr
                      key={i}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-6 py-3 text-sm text-[#666]">{i + 1}</td>
                      <td className="px-6 py-3 font-mono text-sm">{s.usn}</td>
                      <td className="px-6 py-3 text-sm">{s.name}</td>
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
            <p className="text-[#999]">Importing students...</p>
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
                      <th className="px-6 py-3">USN</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.results.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-3 font-mono text-sm">{r.usn}</td>
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
