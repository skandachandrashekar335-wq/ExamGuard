"use client";

interface HallTicketVizProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
}

interface FieldRow {
  label: string;
  value: string;
  status: "empty" | "loading" | "connected";
}

export default function HallTicketViz({ stage }: HallTicketVizProps) {
  const isActive = stage !== "ready";

  const studentFields: FieldRow[] = [
    { label: "STUDENT", value: "NOT CONNECTED", status: "empty" },
    { label: "REGISTRATION", value: "AWAITING DATA", status: "empty" },
  ];

  const examFields: FieldRow[] = [
    { label: "EXAM", value: "AWAITING DATA", status: "empty" },
    { label: "HALL TICKET", value: "NOT LOADED", status: "empty" },
  ];

  return (
    <div className="eg-card relative overflow-hidden">
      <div className="absolute inset-0 eg-grid-fine opacity-30" />

      <div className="relative">
        <div className="eg-label mb-4">HALL TICKET CONTEXT</div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            {studentFields.map((f) => (
              <div key={f.label} className="mb-3">
                <div className="eg-label text-[0.6rem] mb-1">{f.label}</div>
                <div
                  className={`font-mono text-sm ${
                    isActive ? "text-[var(--text-secondary)]" : "text-[var(--text-tertiary)]"
                  }`}
                  style={{ transition: "color 0.5s ease" }}
                >
                  {f.value}
                </div>
              </div>
            ))}
          </div>
          <div>
            {examFields.map((f) => (
              <div key={f.label} className="mb-3">
                <div className="eg-label text-[0.6rem] mb-1">{f.label}</div>
                <div
                  className={`font-mono text-sm ${
                    isActive ? "text-[var(--text-secondary)]" : "text-[var(--text-tertiary)]"
                  }`}
                  style={{ transition: "color 0.5s ease" }}
                >
                  {f.value}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Relationship arrows */}
        <div className="flex items-center justify-center gap-3 py-4">
          <div className={`eg-label text-[0.6rem] ${stage === "verify" || stage === "decide" || stage === "authorize" ? "eg-stage-active" : ""}`}>
            HALL TICKET
          </div>
          <div className="flex items-center gap-1">
            <div className={`w-8 h-px ${stage === "verify" || stage === "decide" || stage === "authorize" ? "bg-[var(--accent-cyan)]" : "bg-[var(--text-tertiary)]"}`} style={{ transition: "background 0.5s ease" }} />
            <span className="text-[var(--text-tertiary)] text-xs">+</span>
            <div className={`w-8 h-px ${stage === "verify" || stage === "decide" || stage === "authorize" ? "bg-[var(--accent-cyan)]" : "bg-[var(--text-tertiary)]"}`} style={{ transition: "background 0.5s ease" }} />
          </div>
          <div className={`eg-label text-[0.6rem] ${stage === "verify" || stage === "decide" || stage === "authorize" ? "eg-stage-active" : ""}`}>
            IDENTITY
          </div>
          <div className="flex items-center gap-1">
            <div className={`w-8 h-px ${stage === "decide" || stage === "authorize" ? "bg-[var(--accent-emerald)]" : "bg-[var(--text-tertiary)]"}`} style={{ transition: "background 0.5s ease" }} />
            <span className="text-[var(--text-tertiary)] text-xs">↓</span>
          </div>
          <div className={`eg-label text-[0.6rem] ${stage === "decide" || stage === "authorize" ? "eg-stage-active" : ""}`}>
            VERIFICATION
          </div>
          <div className="flex items-center gap-1">
            <div className={`w-8 h-px ${stage === "authorize" ? "bg-[var(--accent-amber)]" : "bg-[var(--text-tertiary)]"}`} style={{ transition: "background 0.5s ease" }} />
            <span className="text-[var(--text-tertiary)] text-xs">↓</span>
          </div>
          <div className={`eg-label text-[0.6rem] ${stage === "authorize" ? "eg-stage-active" : ""}`}>
            DECISION
          </div>
        </div>

        <div className="text-center mt-2">
          <span className={`eg-label text-[0.6rem] ${stage === "authorize" ? "text-[var(--accent-amber)]" : ""}`}>
            {stage === "ready" && "HALL TICKET + IDENTITY → VERIFICATION → DECISION"}
            {stage === "detect" && "HALL TICKET + IDENTITY → VERIFICATION → DECISION"}
            {stage === "verify" && "AWAITING VERIFICATION INPUT"}
            {stage === "decide" && "EVIDENCE ≠ DECISION"}
            {stage === "authorize" && "AWAITING VERIFIED DECISION"}
          </span>
        </div>
      </div>
    </div>
  );
}
