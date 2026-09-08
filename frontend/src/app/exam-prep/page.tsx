"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiRequest, qs } from "@/lib/api";

interface Exam {
  id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  status: string;
}

interface Student {
  id: number;
  usn: string;
  name: string;
  is_active: boolean;
}

interface ExamHall {
  id: number;
  hall_name: string;
  building: string | null;
  room_number: string | null;
  capacity: number;
  is_active: boolean;
}

interface HallTicket {
  id: number;
  student_id: number;
  exam_id: number;
  status: string;
  ticket_number: string | null;
}

interface SeatAssignment {
  id: number;
  student_id: number;
  exam_hall_id: number;
  exam_id: number;
  seat_number: string;
  row_number: string | null;
}

interface EntryPoint {
  id: number;
  code: string;
  name: string;
  exam_hall_id: number;
}

interface Camera {
  id: number;
  name: string;
  status: string;
}

interface Document {
  id: number;
  filename: string;
  document_type: string;
  status: string;
  processing_status: string | null;
}

const STEPS = [
  { id: 1, label: "Exam Details", key: "exam" },
  { id: 2, label: "Hall Tickets", key: "tickets" },
  { id: 3, label: "Students", key: "students" },
  { id: 4, label: "Seating", key: "seating" },
  { id: 5, label: "Halls & Entry", key: "halls" },
  { id: 6, label: "Cameras", key: "cameras" },
  { id: 7, label: "Validation", key: "validate" },
  { id: 8, label: "Ready", key: "ready" },
];

export default function ExamPrepPage() {
  const [step, setStep] = useState(1);
  const [exams, setExams] = useState<Exam[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [halls, setHalls] = useState<ExamHall[]>([]);
  const [tickets, setTickets] = useState<HallTicket[]>([]);
  const [seats, setSeats] = useState<SeatAssignment[]>([]);
  const [entryPoints, setEntryPoints] = useState<EntryPoint[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedExam = exams.find((e) => e.id === selectedExamId);

  const loadExams = useCallback(async () => {
    try {
      const data = await apiRequest<{ items: Exam[] }>("/api/v1/exams?page_size=100");
      setExams(data.items || []);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const loadExamData = useCallback(async (examId: number) => {
    setLoading(true);
    setError(null);
    try {
      const [regData, hallData, ticketData, seatData, epData, camData, docData] = await Promise.all([
        apiRequest<{ items: Student[] }>(`/api/v1/exam-registrations${qs({ exam_id: examId, page_size: 500 })}`).catch(() => ({ items: [] })),
        apiRequest<{ items: ExamHall[] }>("/api/v1/exam-halls?page_size=100").catch(() => ({ items: [] })),
        apiRequest<{ items: HallTicket[] }>(`/api/v1/hall-tickets${qs({ exam_id: examId, page_size: 500 })}`).catch(() => ({ items: [] })),
        apiRequest<{ items: SeatAssignment[] }>(`/api/v1/seat-assignments${qs({ exam_id: examId, page_size: 500 })}`).catch(() => ({ items: [] })),
        apiRequest<{ items: EntryPoint[] }>("/api/v1/entry-points?page_size=100").catch(() => ({ items: [] })),
        apiRequest<{ items: Camera[] }>("/api/v1/cameras?page_size=100").catch(() => ({ items: [] })),
        apiRequest<{ items: Document[] }>(`/api/v1/documents${qs({ exam_id: examId, page_size: 100 })}`).catch(() => ({ items: [] })),
      ]);

      setHalls(hallData.items || []);
      setTickets(ticketData.items || []);
      setSeats(seatData.items || []);
      setEntryPoints(epData.items || []);
      setCameras(camData.items || []);
      setDocuments(docData.items || []);

      const studentIds = new Set((regData.items || []).map((r: any) => r.student_id));
      if (studentIds.size > 0) {
        const studentData = await apiRequest<{ items: Student[] }>(
          `/api/v1/students?page_size=500`
        ).catch(() => ({ items: [] }));
        setStudents(studentData.items.filter((s) => studentIds.has(s.id)));
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadExams(); }, [loadExams]);
  useEffect(() => { if (selectedExamId) loadExamData(selectedExamId); }, [selectedExamId, loadExamData]);

  const examStudents = students;
  const examTickets = tickets.filter((t) => t.exam_id === selectedExamId);
  const examSeats = seats.filter((s) => s.exam_id === selectedExamId);
  const hallTickets = documents.filter((d) => d.document_type === "HALL_TICKET");

  const validatedHalls = halls.filter((h) => {
    const hallEPs = entryPoints.filter((ep) => ep.exam_hall_id === h.id);
    const hallCameras = cameras.filter((c) => hallEPs.some((ep) => ep.id));
    return hallEPs.length > 0 && hallCameras.length > 0;
  });

  const readiness = {
    exam: !!selectedExam,
    tickets: examTickets.length > 0,
    students: examStudents.length > 0,
    seating: examSeats.length > 0,
    halls: validatedHalls.length > 0,
    cameras: cameras.filter((c) => c.status === "ACTIVE").length > 0,
  };

  const allReady = Object.values(readiness).every(Boolean);

  return (
    <div className="eg-page">
      <div className="eg-page-header">
        <Link href="/exams" className="eg-breadcrumb">← Back to Examinations</Link>
        <h1 className="eg-page-title">Prepare Examination</h1>
        <p className="eg-page-desc">
          Configure an examination step by step. Each step must be completed before the exam is ready.
        </p>
      </div>

      {/* Step indicator */}
      <div className="glass" style={{ padding: "1rem 1.5rem", borderRadius: "var(--radius-lg)", marginBottom: "2rem" }}>
        <div style={{ display: "flex", gap: "0.25rem", overflowX: "auto" }}>
          {STEPS.map((s) => (
            <button
              key={s.id}
              onClick={() => s.id <= step + 1 && setStep(s.id)}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: s.id === step ? "var(--accent)" : s.id < step ? "var(--success-bg)" : "transparent",
                color: s.id === step ? "#fff" : s.id < step ? "var(--success)" : "var(--text-muted)",
                fontSize: "0.75rem",
                fontWeight: 500,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              {s.id < step ? "✓ " : ""}{s.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="eg-alert eg-alert-danger" style={{ marginBottom: "1.5rem" }}>{error}</div>
      )}

      {/* Step 1: Exam Details */}
      {step === 1 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "1rem" }}>Step 1: Select Examination</h2>
          {!selectedExamId ? (
            <div>
              <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>Select an examination to prepare:</p>
              {exams.length === 0 ? (
                <div className="eg-empty">
                  <p className="eg-empty-title">No Examinations Found</p>
                  <p className="eg-empty-desc">Create an examination first.</p>
                  <Link href="/exams" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Create Examination</Link>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {exams.map((exam) => (
                    <button
                      key={exam.id}
                      onClick={() => setSelectedExamId(exam.id)}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "1rem 1.25rem",
                        background: "var(--bg-glass)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-sm)",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "border-color 0.15s ease",
                      }}
                    >
                      <div>
                        <p style={{ fontWeight: 500, color: "var(--text-primary)" }}>{exam.exam_name}</p>
                        <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                          {exam.exam_date} · {exam.start_time} – {exam.end_time}
                        </p>
                      </div>
                      <span className={`eg-badge eg-badge-${exam.status === "SCHEDULED" ? "success" : exam.status === "ACTIVE" ? "info" : "neutral"}`}>
                        {exam.status}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: "1.5rem" }}>
                <div>
                  <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.125rem" }}>{selectedExam?.exam_name}</h3>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                    {selectedExam?.exam_date} · {selectedExam?.start_time} – {selectedExam?.end_time}
                  </p>
                </div>
                <button onClick={() => setSelectedExamId(null)} className="eg-btn eg-btn-sm">Change</button>
              </div>

              <div className="eg-grid-3" style={{ gap: "1rem" }}>
                {[
                  { label: "Hall Tickets", value: examTickets.length, ok: readiness.tickets },
                  { label: "Registered Students", value: examStudents.length, ok: readiness.students },
                  { label: "Seat Assignments", value: examSeats.length, ok: readiness.seating },
                  { label: "Halls Configured", value: validatedHalls.length, ok: readiness.halls },
                  { label: "Entry Points", value: entryPoints.length, ok: entryPoints.length > 0 },
                  { label: "Active Cameras", value: cameras.filter((c) => c.status === "ACTIVE").length, ok: readiness.cameras },
                ].map((item) => (
                  <div key={item.label} className="glass" style={{ padding: "1rem", borderRadius: "var(--radius-md)" }}>
                    <p className="eg-metric-label">{item.label}</p>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                      <span className="eg-metric-value">{item.value}</span>
                      {item.ok ? (
                        <span className="eg-badge eg-badge-success" style={{ fontSize: "0.5rem" }}>OK</span>
                      ) : (
                        <span className="eg-badge eg-badge-warning" style={{ fontSize: "0.5rem" }}>Needed</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
                <button onClick={() => setStep(2)} className="eg-btn eg-btn-primary">Continue to Step 2 →</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Hall Tickets */}
      {step === 2 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "0.5rem" }}>Step 2: Hall Tickets</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Upload and process hall tickets for this examination.
          </p>

          <div className="eg-grid-2" style={{ gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ padding: "1rem", background: "var(--bg-glass-medium)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
              <p className="eg-metric-label">Hall Ticket Documents</p>
              <p className="eg-metric-value">{hallTickets.length}</p>
            </div>
            <div style={{ padding: "1rem", background: "var(--bg-glass-medium)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
              <p className="eg-metric-label">Processed Tickets</p>
              <p className="eg-metric-value">{examTickets.length}</p>
            </div>
          </div>

          {hallTickets.length === 0 ? (
            <div className="eg-empty" style={{ padding: "2rem" }}>
              <p className="eg-empty-title">No Hall Tickets Uploaded</p>
              <p className="eg-empty-desc">Upload hall ticket documents to extract candidate data.</p>
              <Link href="/documents" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Upload Documents</Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {hallTickets.map((doc) => (
                <div key={doc.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.75rem 1rem", background: "var(--bg-glass)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                  <div>
                    <p style={{ fontWeight: 500, fontSize: "0.875rem" }}>{doc.filename}</p>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{doc.processing_status || doc.status}</p>
                  </div>
                  <span className={`eg-badge eg-badge-${doc.status === "VERIFIED" ? "success" : doc.status === "FAILED" ? "danger" : "neutral"}`}>
                    {doc.status}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
            <button onClick={() => setStep(1)} className="eg-btn">← Back</button>
            <button onClick={() => setStep(3)} className="eg-btn eg-btn-primary" disabled={examTickets.length === 0}>
              {examTickets.length === 0 ? "Upload Hall Tickets First" : "Continue to Step 3 →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Students */}
      {step === 3 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "0.5rem" }}>Step 3: Registered Students</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Students registered for this examination.
          </p>

          {examStudents.length === 0 ? (
            <div className="eg-empty" style={{ padding: "2rem" }}>
              <p className="eg-empty-title">No Students Registered</p>
              <p className="eg-empty-desc">Register students for this examination.</p>
              <Link href="/import/registrations" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Import Registrations</Link>
            </div>
          ) : (
            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th>USN</th>
                    <th>Name</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {examStudents.slice(0, 50).map((s) => (
                    <tr key={s.id}>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>{s.usn}</td>
                      <td>{s.name}</td>
                      <td><span className="eg-badge eg-badge-success">Registered</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
            <button onClick={() => setStep(2)} className="eg-btn">← Back</button>
            <button onClick={() => setStep(4)} className="eg-btn eg-btn-primary" disabled={examStudents.length === 0}>
              {examStudents.length === 0 ? "Register Students First" : "Continue to Step 4 →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Seating */}
      {step === 4 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "0.5rem" }}>Step 4: Seating Arrangement</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Map students to halls and seats.
          </p>

          <div className="eg-grid-2" style={{ gap: "1rem", marginBottom: "1.5rem" }}>
            <div style={{ padding: "1rem", background: "var(--bg-glass-medium)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
              <p className="eg-metric-label">Assigned Seats</p>
              <p className="eg-metric-value">{examSeats.length}</p>
            </div>
            <div style={{ padding: "1rem", background: "var(--bg-glass-medium)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
              <p className="eg-metric-label">Students Without Seats</p>
              <p className="eg-metric-value" style={{ color: examStudents.length - examSeats.length > 0 ? "var(--warning)" : "var(--success)" }}>
                {examStudents.length - examSeats.length}
              </p>
            </div>
          </div>

          {examSeats.length === 0 ? (
            <div className="eg-empty" style={{ padding: "2rem" }}>
              <p className="eg-empty-title">No Seating Arrangement</p>
              <p className="eg-empty-desc">Upload or configure seating arrangement for this examination.</p>
              <Link href="/import/seat-assignments" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Import Seating</Link>
            </div>
          ) : (
            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Hall</th>
                    <th>Seat</th>
                  </tr>
                </thead>
                <tbody>
                  {examSeats.slice(0, 50).map((s) => {
                    const student = students.find((st) => st.id === s.student_id);
                    const hall = halls.find((h) => h.id === s.exam_hall_id);
                    return (
                      <tr key={s.id}>
                        <td>{student?.usn || `Student #${s.student_id}`}</td>
                        <td>{hall?.hall_name || `Hall #${s.exam_hall_id}`}</td>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>{s.seat_number}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
            <button onClick={() => setStep(3)} className="eg-btn">← Back</button>
            <button onClick={() => setStep(5)} className="eg-btn eg-btn-primary" disabled={examSeats.length === 0}>
              {examSeats.length === 0 ? "Assign Seats First" : "Continue to Step 5 →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 5: Halls & Entry Points */}
      {step === 5 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "0.5rem" }}>Step 5: Halls & Entry Points</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Configure examination halls and their entry points.
          </p>

          {halls.length === 0 ? (
            <div className="eg-empty" style={{ padding: "2rem" }}>
              <p className="eg-empty-title">No Examination Halls</p>
              <p className="eg-empty-desc">Create examination halls first.</p>
              <Link href="/exam-halls" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Manage Halls</Link>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {halls.map((hall) => {
                const hallEPs = entryPoints.filter((ep) => ep.exam_hall_id === hall.id);
                return (
                  <div key={hall.id} style={{ padding: "1rem", background: "var(--bg-glass)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                      <div>
                        <p style={{ fontWeight: 500 }}>{hall.hall_name}</p>
                        <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                          {hall.building} {hall.room_number} · Capacity: {hall.capacity}
                        </p>
                      </div>
                      <span className={`eg-badge eg-badge-${hallEPs.length > 0 ? "success" : "warning"}`}>
                        {hallEPs.length} entry point{hallEPs.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    {hallEPs.length > 0 && (
                      <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                        {hallEPs.map((ep) => (
                          <span key={ep.id} className="eg-badge eg-badge-info" style={{ fontSize: "0.5rem" }}>
                            {ep.code}: {ep.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
            <button onClick={() => setStep(4)} className="eg-btn">← Back</button>
            <button onClick={() => setStep(6)} className="eg-btn eg-btn-primary" disabled={validatedHalls.length === 0}>
              {validatedHalls.length === 0 ? "Configure Halls & Entry Points First" : "Continue to Step 6 →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 6: Cameras */}
      {step === 6 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "0.5rem" }}>Step 6: Cameras</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Configure cameras for entry verification.
          </p>

          {cameras.length === 0 ? (
            <div className="eg-empty" style={{ padding: "2rem" }}>
              <p className="eg-empty-title">No Cameras Configured</p>
              <p className="eg-empty-desc">Add cameras for entry point verification.</p>
              <Link href="/cameras" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Manage Cameras</Link>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "0.75rem" }}>
              {cameras.map((cam) => (
                <div key={cam.id} style={{ padding: "1rem", background: "var(--bg-glass)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                  <p style={{ fontWeight: 500, fontSize: "0.875rem" }}>{cam.name}</p>
                  <span className={`eg-badge eg-badge-${cam.status === "ACTIVE" ? "success" : cam.status === "INACTIVE" ? "danger" : "neutral"}`} style={{ marginTop: "0.375rem" }}>
                    {cam.status}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
            <button onClick={() => setStep(5)} className="eg-btn">← Back</button>
            <button onClick={() => setStep(7)} className="eg-btn eg-btn-primary" disabled={cameras.filter((c) => c.status === "ACTIVE").length === 0}>
              {cameras.filter((c) => c.status === "ACTIVE").length === 0 ? "Configure Active Cameras First" : "Continue to Validation →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 7: Validation */}
      {step === 7 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", marginBottom: "0.5rem" }}>Step 7: Validation</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
            Validate that all prerequisites are met.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {[
              { label: "Exam configured", ok: readiness.exam, detail: selectedExam?.exam_name },
              { label: "Hall tickets processed", ok: readiness.tickets, detail: `${hallTickets.length} document(s)` },
              { label: "Students registered", ok: readiness.students, detail: `${examStudents.length} student(s)` },
              { label: "Seating validated", ok: readiness.seating, detail: `${examSeats.length} seat(s)` },
              { label: "Halls configured", ok: readiness.halls, detail: `${validatedHalls.length} hall(s) with entry points` },
              { label: "Cameras configured", ok: readiness.cameras, detail: `${cameras.filter((c) => c.status === "ACTIVE").length} active camera(s)` },
            ].map((item) => (
              <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1rem", background: "var(--bg-glass)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                <span style={{ fontSize: "1.25rem" }}>{item.ok ? "✅" : "⚠️"}</span>
                <div style={{ flex: 1 }}>
                  <p style={{ fontWeight: 500, fontSize: "0.875rem" }}>{item.label}</p>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{item.detail}</p>
                </div>
                <span className={`eg-badge eg-badge-${item.ok ? "success" : "warning"}`}>
                  {item.ok ? "PASS" : "INCOMPLETE"}
                </span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.75rem" }}>
            <button onClick={() => setStep(6)} className="eg-btn">← Back</button>
            {allReady ? (
              <button onClick={() => setStep(8)} className="eg-btn eg-btn-primary">Mark Ready →</button>
            ) : (
              <button disabled className="eg-btn" style={{ opacity: 0.5 }}>Complete all steps first</button>
            )}
          </div>
        </div>
      )}

      {/* Step 8: Ready */}
      {step === 8 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)", textAlign: "center" }}>
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>✅</div>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", marginBottom: "0.5rem" }}>Examination Ready</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "2rem" }}>
            <strong>{selectedExam?.exam_name}</strong> is configured and ready for exam day.
          </p>

          <div className="eg-grid-3" style={{ gap: "1rem", marginBottom: "2rem", textAlign: "left" }}>
            <div className="glass" style={{ padding: "1rem", borderRadius: "var(--radius-sm)" }}>
              <p className="eg-metric-label">Students</p>
              <p className="eg-metric-value">{examStudents.length}</p>
            </div>
            <div className="glass" style={{ padding: "1rem", borderRadius: "var(--radius-sm)" }}>
              <p className="eg-metric-label">Halls</p>
              <p className="eg-metric-value">{validatedHalls.length}</p>
            </div>
            <div className="glass" style={{ padding: "1rem", borderRadius: "var(--radius-sm)" }}>
              <p className="eg-metric-label">Seats</p>
              <p className="eg-metric-value">{examSeats.length}</p>
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center" }}>
            <Link href="/examination-sessions" className="eg-btn eg-btn-primary">Start Examination Session</Link>
            <Link href="/dashboard" className="eg-btn">Back to Dashboard</Link>
          </div>
        </div>
      )}
    </div>
  );
}
