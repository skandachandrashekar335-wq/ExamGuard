"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import * as XLSX from "xlsx";
import {
  parseSpreadsheet,
  validateRows,
  exportFailedRows,
  sheetDateToString,
  sheetTimeToString,
  type ValidationError,
} from "@/lib/spreadsheet";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_SUBJECTS = 200;
const MAX_EXAMS = 500;

const SUBJECT_HEADERS = ["Code", "Name", "Department", "Semester", "Credits"];
const SUBJECT_REQUIRED = ["Code", "Name", "Department", "Semester"];

const EXAM_HEADERS = [
  "Subject Code",
  "Exam Name",
  "Exam Date",
  "Start Time",
  "End Time",
  "Semester",
  "Department",
];
const EXAM_REQUIRED = [
  "Subject Code",
  "Exam Name",
  "Exam Date",
  "Start Time",
  "End Time",
  "Semester",
  "Department",
];

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

interface RowState {
  row: Record<string, unknown>;
  errors: ValidationError[];
  valid: boolean;
  type: "subject" | "exam";
}

export default function ImportSubjectsExamsPage() {
  const [phase, setPhase] = useState<Phase>("select");
  const [subjects, setSubjects] = useState<RowState[]>([]);
  const [exams, setExams] = useState<RowState[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<ImportResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<"subjects" | "exams">("subjects");

  const validSubjects = subjects.filter((r) => r.valid).length;
  const invalidSubjects = subjects.filter((r) => !r.valid).length;
  const validExams = exams.filter((r) => r.valid).length;
  const invalidExams = exams.filter((r) => !r.valid).length;

  const reset = useCallback(() => {
    setPhase("select");
    setSubjects([]);
    setExams([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    setActiveTab("subjects");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setParseError("");
    setSubjects([]);
    setExams([]);

    try {
      const { rows: data } = await parseSpreadsheet(file);

      if (data.length === 0) {
        setParseError("File contains no data rows");
        return;
      }

      const hasSubjectCols = SUBJECT_REQUIRED.every((c) =>
        Object.keys(data[0]).some((k) => k.trim().toLowerCase() === c.toLowerCase())
      );
      const hasExamCols = EXAM_REQUIRED.every((c) =>
        Object.keys(data[0]).some((k) => k.trim().toLowerCase() === c.toLowerCase())
      );

      if (!hasSubjectCols && !hasExamCols) {
        setParseError(
          "File must contain either subject columns (Code, Name, Department, Semester) or exam columns (Subject Code, Exam Name, Exam Date, Start Time, End Time, Semester, Department)"
        );
        return;
      }

      if (hasSubjectCols) {
        if (data.length > MAX_SUBJECTS) {
          setParseError(`Too many subject rows: ${data.length} (max ${MAX_SUBJECTS})`);
          return;
        }
        const result = validateRows<SubjectItem>(
          data,
          SUBJECT_REQUIRED,
          (row) => {
            const errors: ValidationError[] = [];
            const sem = Number(row["Semester"]);
            if (!Number.isInteger(sem) || sem < 1 || sem > 8) {
              errors.push({ row: 0, column: "Semester", message: "Semester must be an integer between 1 and 8" });
            }
            const credits = row["Credits"];
            if (credits !== undefined && credits !== "" && credits !== null) {
              const c = Number(credits);
              if (!Number.isInteger(c) || c <= 0) {
                errors.push({ row: 0, column: "Credits", message: "Credits must be a positive integer" });
              }
            }
            return errors;
          },
          (row) => ({
            code: String(row["Code"] ?? "").trim(),
            name: String(row["Name"] ?? "").trim(),
            department: String(row["Department"] ?? "").trim(),
            semester: Number(row["Semester"]),
            credits: row["Credits"] ? Number(row["Credits"]) : undefined,
          })
        );

        setSubjects(
          data.map((row, i) => {
            const found = result.allRows[i];
            return { row, errors: found?.errors ?? [], valid: found?.valid ?? true, type: "subject" as const };
          })
        );
      }

      if (hasExamCols) {
        if (data.length > MAX_EXAMS) {
          setParseError(`Too many exam rows: ${data.length} (max ${MAX_EXAMS})`);
          return;
        }
        const result = validateRows<ExamItem>(
          data,
          EXAM_REQUIRED,
          (row) => {
            const errors: ValidationError[] = [];
            const sem = Number(row["Semester"]);
            if (!Number.isInteger(sem) || sem < 1 || sem > 8) {
              errors.push({ row: 0, column: "Semester", message: "Semester must be an integer between 1 and 8" });
            }
            const dateStr = sheetDateToString(row["Exam Date"]);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
              errors.push({ row: 0, column: "Exam Date", message: "Date must be in YYYY-MM-DD format" });
            }
            return errors;
          },
          (row) => ({
            subject_code: String(row["Subject Code"] ?? "").trim(),
            exam_name: String(row["Exam Name"] ?? "").trim(),
            exam_date: sheetDateToString(row["Exam Date"]),
            start_time: sheetTimeToString(row["Start Time"]),
            end_time: sheetTimeToString(row["End Time"]),
            semester: Number(row["Semester"]),
            department: String(row["Department"] ?? "").trim(),
          })
        );

        setExams(
          data.map((row, i) => {
            const found = result.allRows[i];
            return { row, errors: found?.errors ?? [], valid: found?.valid ?? true, type: "exam" as const };
          })
        );
      }

      if (hasSubjectCols && !hasExamCols) setActiveTab("subjects");
      else if (hasExamCols && !hasSubjectCols) setActiveTab("exams");
      else setActiveTab("subjects");

      setPhase("preview");
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Failed to parse file");
    }
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

    const validSubj: SubjectItem[] = subjects
      .filter((r) => r.valid)
      .map((r) => ({
        code: String(r.row["Code"] ?? "").trim(),
        name: String(r.row["Name"] ?? "").trim(),
        department: String(r.row["Department"] ?? "").trim(),
        semester: Number(r.row["Semester"]),
        credits: r.row["Credits"] ? Number(r.row["Credits"]) : undefined,
      }));

    const validExam: ExamItem[] = exams
      .filter((r) => r.valid)
      .map((r) => ({
        subject_code: String(r.row["Subject Code"] ?? "").trim(),
        exam_name: String(r.row["Exam Name"] ?? "").trim(),
        exam_date: sheetDateToString(r.row["Exam Date"]),
        start_time: sheetTimeToString(r.row["Start Time"]),
        end_time: sheetTimeToString(r.row["End Time"]),
        semester: Number(r.row["Semester"]),
        department: String(r.row["Department"] ?? "").trim(),
      }));

    if (validSubj.length === 0 && validExam.length === 0) {
      setSubmitError("No valid rows to import");
      setPhase("preview");
      return;
    }

    try {
      const body: Record<string, unknown> = {};
      if (validSubj.length > 0) body.subjects = validSubj;
      if (validExam.length > 0) body.exams = validExam;

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

  const handleDownloadTemplate = () => {
    const wb = XLSX.utils.book_new();

    const subjData = [
      SUBJECT_HEADERS,
      ["CS501", "Data Structures", "Computer Science", 3, 4],
      ["CS502", "Algorithms", "Computer Science", 4, 3],
    ];
    const wsSubj = XLSX.utils.aoa_to_sheet(subjData);
    wsSubj["!cols"] = SUBJECT_HEADERS.map(() => ({ wch: 20 }));
    XLSX.utils.book_append_sheet(wb, wsSubj, "Subjects");

    const examData = [
      EXAM_HEADERS,
      ["CS501", "Midterm Exam", "2026-10-15", "10:00", "12:00", 3, "Computer Science"],
    ];
    const wsExam = XLSX.utils.aoa_to_sheet(examData);
    wsExam["!cols"] = EXAM_HEADERS.map(() => ({ wch: 20 }));
    XLSX.utils.book_append_sheet(wb, wsExam, "Exams");

    const instructions = [
      ["Column", "Sheet", "Description"],
      ["Code", "Subjects", "Subject code, e.g. CS501 (required, max 20 chars)"],
      ["Name", "Subjects", "Subject name (required, max 255 chars)"],
      ["Department", "Both", "Department offering the subject (required, max 100 chars)"],
      ["Semester", "Both", "Semester number 1-8 (required)"],
      ["Credits", "Subjects", "Credit hours (optional, positive integer)"],
      ["Subject Code", "Exams", "Must match a Subject Code from the Subjects sheet"],
      ["Exam Name", "Exams", "Name of the exam (required)"],
      ["Exam Date", "Exams", "Date in YYYY-MM-DD format (required)"],
      ["Start Time", "Exams", "Time in HH:MM format (required)"],
      ["End Time", "Exams", "Time in HH:MM format (required)"],
    ];
    const wsInst = XLSX.utils.aoa_to_sheet(instructions);
    wsInst["!cols"] = [{ wch: 18 }, { wch: 12 }, { wch: 60 }];
    XLSX.utils.book_append_sheet(wb, wsInst, "Instructions");

    XLSX.writeFile(wb, "subjects_exams_template.xlsx");
  };

  const handleExportFailed = (type: "subjects" | "exams") => {
    const source = type === "subjects" ? subjects : exams;
    const headers = type === "subjects" ? SUBJECT_HEADERS : EXAM_HEADERS;
    const failed = source.filter((r) => !r.valid);
    exportFailedRows(
      failed.map((f) => ({ row: f.row, errors: f.errors })),
      headers
    );
  };

  const displayRows = activeTab === "subjects" ? subjects : exams;
  const displayValid = activeTab === "subjects" ? validSubjects : validExams;
  const displayInvalid = activeTab === "subjects" ? invalidSubjects : invalidExams;
  const displayHeaders = activeTab === "subjects" ? SUBJECT_HEADERS : EXAM_HEADERS;

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Import Subjects &amp; Exams
        </h1>
        <p className="text-[#999] mb-8">
          Upload an Excel or CSV file to bulk import subjects (max {MAX_SUBJECTS}) and exams (max {MAX_EXAMS})
        </p>

        {phase === "select" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">How to import</h2>
              <ol className="text-sm text-[#999] space-y-2 list-decimal list-inside">
                <li>Download the template file below</li>
                <li>Fill in the Subjects sheet and/or Exams sheet</li>
                <li>Save as .xlsx or .csv and upload</li>
                <li>Review the preview and click Import</li>
              </ol>
              <button
                onClick={handleDownloadTemplate}
                className="mt-4 border border-cyan-500/50 text-cyan-400 px-4 py-2 rounded-lg text-sm hover:bg-cyan-500/10 transition-colors"
              >
                Download Template
              </button>
            </div>

            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed border-white/20 rounded-lg p-16 text-center hover:border-white/40 transition-colors cursor-pointer"
              onClick={() => fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx,.csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFile(file);
                }}
              />
              <p className="text-[#999] text-lg mb-2">Drop an Excel or CSV file here</p>
              <p className="text-[#666] text-sm">Accepts .xlsx and .csv files</p>
            </div>
          </div>
        )}

        {parseError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mb-6">
            <p className="text-pink-400 text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && (
          <div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex gap-6 text-sm">
                  {subjects.length > 0 && (
                    <span className="text-[#999]">
                      Subjects: <span className="text-emerald-400">{validSubjects} valid</span>
                      {invalidSubjects > 0 && <span className="text-pink-400">, {invalidSubjects} errors</span>}
                    </span>
                  )}
                  {exams.length > 0 && (
                    <span className="text-[#999]">
                      Exams: <span className="text-emerald-400">{validExams} valid</span>
                      {invalidExams > 0 && <span className="text-pink-400">, {invalidExams} errors</span>}
                    </span>
                  )}
                </div>
                <div className="flex gap-3">
                  {displayInvalid > 0 && (
                    <button onClick={() => handleExportFailed(activeTab)} className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5">
                      Export Failed Rows
                    </button>
                  )}
                  <button onClick={reset} className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5">
                    Cancel
                  </button>
                  {validSubjects + validExams > 0 && (
                    <button onClick={handleSubmit} className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90">
                      Import All
                    </button>
                  )}
                </div>
              </div>
            </div>

            {subjects.length > 0 && exams.length > 0 && (
              <div className="flex gap-2 mb-6">
                <button onClick={() => setActiveTab("subjects")} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === "subjects" ? "bg-white/10 text-white" : "text-[#666] hover:text-white"}`}>
                  Subjects ({subjects.length})
                </button>
                <button onClick={() => setActiveTab("exams")} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === "exams" ? "bg-white/10 text-white" : "text-[#666] hover:text-white"}`}>
                  Exams ({exams.length})
                </button>
              </div>
            )}

            {displayInvalid > 0 && (
              <div className="mb-6">
                <h2 className="text-lg font-semibold mb-3 text-pink-400">Rows With Errors ({displayInvalid})</h2>
                <div className="bg-[#111] border border-pink-500/30 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                        <th className="px-6 py-3">Row</th>
                        {displayHeaders.map((h) => (<th key={h} className="px-6 py-3">{h}</th>))}
                        <th className="px-6 py-3">Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {displayRows.filter((r) => !r.valid).map((r, i) => (
                        <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                          <td className="px-6 py-3 text-sm text-[#666]">{displayRows.indexOf(r) + 1}</td>
                          {displayHeaders.map((h) => (<td key={h} className="px-6 py-3 text-sm">{String(r.row[h] ?? "")}</td>))}
                          <td className="px-6 py-3 text-sm text-pink-400">{r.errors.map((e) => e.message).join("; ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {displayValid > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3 text-emerald-400">Valid Rows ({displayValid})</h2>
                <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                        <th className="px-6 py-3">Row</th>
                        {displayHeaders.map((h) => (<th key={h} className="px-6 py-3">{h}</th>))}
                      </tr>
                    </thead>
                    <tbody>
                      {displayRows.filter((r) => r.valid).map((r, i) => (
                        <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                          <td className="px-6 py-3 text-sm text-[#666]">{displayRows.indexOf(r) + 1}</td>
                          {displayHeaders.map((h) => (<td key={h} className="px-6 py-3 text-sm">{String(r.row[h] ?? "")}</td>))}
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
                {[{ label: "Total", value: response.subject_total, color: "text-white" }, { label: "Created", value: response.subject_created, color: "text-emerald-400" }, { label: "Skipped", value: response.subject_skipped, color: "text-amber-400" }, { label: "Failed", value: response.subject_failed, color: "text-pink-400" }].map((stat) => (
                  <div key={stat.label} className="bg-[#111] border border-white/10 rounded-lg p-4 text-center">
                    <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                    <p className="text-[#999] text-sm">{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-3">Exams</h2>
              <div className="grid grid-cols-4 gap-4">
                {[{ label: "Total", value: response.exam_total, color: "text-white" }, { label: "Created", value: response.exam_created, color: "text-emerald-400" }, { label: "Skipped", value: response.exam_skipped, color: "text-amber-400" }, { label: "Failed", value: response.exam_failed, color: "text-pink-400" }].map((stat) => (
                  <div key={stat.label} className="bg-[#111] border border-white/10 rounded-lg p-4 text-center">
                    <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                    <p className="text-[#999] text-sm">{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>
            {response.subject_results.length > 0 && (
              <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
                <table className="w-full">
                  <thead><tr className="border-b border-white/10 text-left text-sm text-[#999]"><th className="px-6 py-3">Code</th><th className="px-6 py-3">Department</th><th className="px-6 py-3">Status</th><th className="px-6 py-3">Error</th></tr></thead>
                  <tbody>
                    {response.subject_results.map((r, i) => (
                      <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                        <td className="px-6 py-3 font-mono text-sm">{r.code}</td>
                        <td className="px-6 py-3 text-sm text-[#999]">{r.department}</td>
                        <td className="px-6 py-3"><span className={`text-xs px-2 py-1 rounded-full ${r.status === "created" ? "bg-emerald-500/20 text-emerald-400" : r.status === "skipped" ? "bg-amber-500/20 text-amber-400" : "bg-pink-500/20 text-pink-400"}`}>{r.status}</span></td>
                        <td className="px-6 py-3 text-sm text-[#999]">{r.error || "\u2014"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {response.exam_results.length > 0 && (
              <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden mb-6">
                <table className="w-full">
                  <thead><tr className="border-b border-white/10 text-left text-sm text-[#999]"><th className="px-6 py-3">Subject</th><th className="px-6 py-3">Exam Name</th><th className="px-6 py-3">Status</th><th className="px-6 py-3">Error</th></tr></thead>
                  <tbody>
                    {response.exam_results.map((r, i) => (
                      <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                        <td className="px-6 py-3 font-mono text-sm">{r.subject_code}</td>
                        <td className="px-6 py-3 text-sm">{r.exam_name}</td>
                        <td className="px-6 py-3"><span className={`text-xs px-2 py-1 rounded-full ${r.status === "created" ? "bg-emerald-500/20 text-emerald-400" : r.status === "skipped" ? "bg-amber-500/20 text-amber-400" : "bg-pink-500/20 text-pink-400"}`}>{r.status}</span></td>
                        <td className="px-6 py-3 text-sm text-[#999]">{r.error || "\u2014"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <button onClick={reset} className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90">Import Another Batch</button>
          </div>
        )}

        {submitError && (
          <div className="bg-pink-500/10 border border-pink-500/30 rounded-lg p-4 mt-4">
            <p className="text-pink-400 text-sm">{submitError}</p>
          </div>
        )}

        <div className="mt-8">
          <Link href="/import" className="text-[#666] hover:text-white text-sm transition-colors">&larr; Back to Import</Link>
        </div>
      </div>
    </div>
  );
}
