"use client";

interface HallTicketVizProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  progress: number;
  subProgress: number;
}

function mapRange(value: number, inMin: number, inMax: number, outMin: number, outMax: number) {
  return Math.max(Math.min(outMin, outMax), Math.min(Math.max(outMin, outMax), outMin + ((value - inMin) / (inMax - inMin)) * (outMax - outMin)));
}

interface FieldRow {
  label: string;
  value: string;
  revealAt: number;
}

const STUDENT_FIELDS: FieldRow[] = [
  { label: "STUDENT", value: "NOT CONNECTED", revealAt: 0.35 },
  { label: "REGISTRATION", value: "AWAITING DATA", revealAt: 0.40 },
];

const EXAM_FIELDS: FieldRow[] = [
  { label: "EXAM", value: "AWAITING DATA", revealAt: 0.42 },
  { label: "HALL TICKET", value: "NOT LOADED", revealAt: 0.45 },
];

const PIPELINE_STEPS = [
  { label: "HALL TICKET", revealAt: 0.30 },
  { label: "IDENTITY", revealAt: 0.38 },
  { label: "VERIFICATION", revealAt: 0.48 },
  { label: "DECISION", revealAt: 0.58 },
];

export default function HallTicketViz({ stage, progress, subProgress }: HallTicketVizProps) {
  const p = progress;

  // Document scan line position (sweeps during detect 10%-30%)
  const scanProgress = mapRange(p, 0.10, 0.30, 0, 1);
  const showScan = p > 0.08 && p < 0.35;

  // Document frame opacity
  const frameOpacity = mapRange(p, 0.05, 0.12, 0, 1);

  // Processing pulse
  const pulseOpacity = (p > 0.15 && p < 0.55) ? mapRange(p, 0.15, 0.25, 0, 0.5) * mapRange(p, 0.5, 0.55, 0.5, 0) : 0;

  return (
    <div className="relative overflow-hidden" style={{ opacity: frameOpacity }}>
      {/* Document frame */}
      <div className="relative border border-[var(--border)] rounded-lg bg-[var(--surface)] overflow-hidden"
        style={{ boxShadow: p > 0.1 ? "0 0 30px rgba(0, 229, 255, 0.05)" : "none" }}>

        {/* Corner marks — technical document feel */}
        <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-[var(--accent-cyan)] opacity-30" />
        <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-[var(--accent-cyan)] opacity-30" />
        <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-[var(--accent-cyan)] opacity-30" />
        <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-[var(--accent-cyan)] opacity-30" />

        {/* Document header */}
        <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${p > 0.2 ? "bg-[var(--accent-cyan)]" : "bg-[var(--text-tertiary)]"}`} style={{ transition: "background 0.5s" }} />
            <span className="eg-label text-[0.6rem]">HALL TICKET CONTEXT</span>
          </div>
          <span className="eg-label text-[0.5rem] opacity-50">
            {p < 0.15 ? "STANDBY" : p < 0.55 ? "PROCESSING" : "AWAITING DATA"}
          </span>
        </div>

        {/* Scan line overlay */}
        {showScan && (
          <div
            className="absolute left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[var(--accent-cyan)] to-transparent z-10 pointer-events-none"
            style={{
              top: `${scanProgress * 100}%`,
              opacity: 0.6,
              boxShadow: "0 0 8px var(--accent-cyan)",
            }}
          />
        )}

        {/* Processing pulse */}
        {pulseOpacity > 0.01 && (
          <div className="absolute inset-0 pointer-events-none" style={{
            background: "radial-gradient(ellipse at center, rgba(0,229,255,0.05) 0%, transparent 70%)",
            opacity: pulseOpacity,
          }} />
        )}

        {/* Field grid */}
        <div className="relative p-4">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {/* Student fields */}
            <div>
              {STUDENT_FIELDS.map((f) => {
                const fieldOpacity = mapRange(p, f.revealAt - 0.05, f.revealAt + 0.05, 0, 1);
                return (
                  <div key={f.label} className="mb-3" style={{ opacity: fieldOpacity }}>
                    <div className="eg-label text-[0.55rem] mb-0.5 flex items-center gap-1">
                      <span className="inline-block w-1 h-1 rounded-full bg-[var(--accent-cyan)]" style={{ opacity: fieldOpacity }} />
                      {f.label}
                    </div>
                    <div className="font-mono text-xs text-[var(--text-tertiary)]" style={{ transition: "color 0.5s" }}>
                      {f.value}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Exam fields */}
            <div>
              {EXAM_FIELDS.map((f) => {
                const fieldOpacity = mapRange(p, f.revealAt - 0.05, f.revealAt + 0.05, 0, 1);
                return (
                  <div key={f.label} className="mb-3" style={{ opacity: fieldOpacity }}>
                    <div className="eg-label text-[0.55rem] mb-0.5 flex items-center gap-1">
                      <span className="inline-block w-1 h-1 rounded-full bg-[var(--accent-emerald)]" style={{ opacity: fieldOpacity }} />
                      {f.label}
                    </div>
                    <div className="font-mono text-xs text-[var(--text-tertiary)]" style={{ transition: "color 0.5s" }}>
                      {f.value}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Processing pipeline */}
          <div className="mt-4 pt-3 border-t border-[var(--border)]">
            <div className="flex items-center justify-between gap-1">
              {PIPELINE_STEPS.map((step, i) => {
                const stepOpacity = mapRange(p, step.revealAt - 0.03, step.revealAt + 0.05, 0, 1);
                const isCurrentStage = (stage === "verify" && i === 1) || (stage === "decide" && i === 3);
                return (
                  <div key={step.label} className="flex items-center gap-1 flex-1">
                    <div className="flex flex-col items-center flex-1">
                      <div
                        className={`w-full h-[2px] rounded-full mb-1 ${
                          stepOpacity > 0.7
                            ? isCurrentStage
                              ? "bg-[var(--accent-cyan)]"
                              : "bg-[var(--accent-emerald)]"
                            : "bg-[var(--text-tertiary)]"
                        }`}
                        style={{ opacity: Math.max(0.15, stepOpacity) }}
                      />
                      <span
                        className="eg-label text-center"
                        style={{
                          fontSize: "0.5rem",
                          color: stepOpacity > 0.7 ? "var(--text-secondary)" : "var(--text-tertiary)",
                          opacity: Math.max(0.3, stepOpacity),
                        }}
                      >
                        {step.label}
                      </span>
                    </div>
                    {i < PIPELINE_STEPS.length - 1 && (
                      <span className="text-[var(--text-tertiary)] text-[0.5rem] mt-[-8px]" style={{ opacity: stepOpacity > 0.5 ? 0.5 : 0.15 }}>
                        →
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Bottom status */}
          <div className="mt-3 text-center">
            <span className="eg-label text-[0.5rem]" style={{
              color: stage === "authorize" ? "var(--accent-amber)" : stage === "decide" ? "var(--accent-emerald)" : "var(--text-tertiary)",
            }}>
              {stage === "ready" && "AWAITING SCANNING"}
              {stage === "detect" && "SCANNING DOCUMENT"}
              {stage === "verify" && "AWAITING VERIFICATION INPUT"}
              {stage === "decide" && "EVIDENCE ≠ DECISION"}
              {stage === "authorize" && "AWAITING VERIFIED DECISION"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
