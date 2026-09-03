"use client";

import { useRef, useEffect, useState } from "react";
import { useScrollProgress, useMouseCSS } from "@/components/useScrollProgress";
import FaceGeometry from "@/components/FaceGeometry";
import HallTicketViz from "@/components/HallTicketViz";
import StageNav from "@/components/StageNav";
import SystemTerminal from "@/components/SystemTerminal";

const STAGE_RANGES: { stage: string; start: number; end: number }[] = [
  { stage: "detect", start: 0.05, end: 0.3 },
  { stage: "verify", start: 0.3, end: 0.55 },
  { stage: "decide", start: 0.55, end: 0.8 },
  { stage: "authorize", start: 0.8, end: 1.0 },
];

export default function Home() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { subscribe, getState } = useScrollProgress(scrollRef);
  useMouseCSS();

  const [scrollState, setScrollState] = useState(() => getState());
  const [initialized, setInitialized] = useState(false);
  const [activeFeature, setActiveFeature] = useState(0);

  useEffect(() => {
    return subscribe(setScrollState);
  }, [subscribe]);

  useEffect(() => {
    if (!initialized && scrollState.progress > 0.01) {
      setInitialized(true);
    }
  }, [scrollState.progress, initialized]);

  useEffect(() => {
    const featureCount = 6;
    const interval = setInterval(() => {
      setActiveFeature((prev) => (prev + 1) % featureCount);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const isScrolling = scrollState.progress > 0.01;
  const { stage, subProgress } = scrollState;

  const interpolate = (a: number, b: number) => a + (b - a) * subProgress;
  const opacityFor = (start: number, peak: number, end: number) => {
    if (scrollState.progress < start) return 0;
    if (scrollState.progress > end) return 0;
    if (scrollState.progress < peak) return interpolate(0, 1);
    return interpolate(1, 0);
  };

  const detectOpacity = opacityFor(0.05, 0.12, 0.28);
  const verifyOpacity = opacityFor(0.3, 0.37, 0.53);
  const decideOpacity = opacityFor(0.55, 0.62, 0.78);
  const authorizeOpacity = opacityFor(0.8, 0.87, 1.0);

  const titleText =
    stage === "ready" ? "SHOULD THIS STUDENT BE HERE?"
    : stage === "detect" ? "IS THIS A REAL PERSON?"
    : stage === "verify" ? "CAN WE PROVE WHO THEY CLAIM TO BE?"
    : stage === "decide" ? "SHOULD THEY BE ALLOWED IN?"
    : "ENTRY SHOULD BE VERIFIED.";

  const titleSubtext =
    stage === "ready" ? "Scroll to begin the verification experience"
    : stage === "detect" ? "Facial liveness + anti-spoofing detection"
    : stage === "verify" ? "1:N identity matching against enrollment"
    : stage === "decide" ? "Evidence threshold evaluation"
    : "No spoofing. No proxy. No compromise.";

  return (
    <>
      <div
        ref={scrollRef}
        style={{ height: "500vh" }}
        className="relative"
      >
        <div className="eg-sticky h-screen w-full overflow-hidden">

          {/* Power-up overlay */}
          <div
            className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[var(--bg-base)] transition-opacity duration-700"
            style={{
              opacity: initialized ? 0 : 1,
              pointerEvents: initialized ? "none" : "auto",
            }}
          >
            <div className="relative">
              <svg viewBox="0 0 64 64" className="w-12 h-12 mb-4 mx-auto" style={{ opacity: 0.6 }}>
                <circle cx="32" cy="24" r="12" stroke="var(--accent-cyan)" strokeWidth="1.5" fill="none" strokeDasharray="4 3" className="animate-spin" style={{ animationDuration: "8s" }} />
                <circle cx="32" cy="24" r="5" fill="var(--accent-cyan)" opacity={0.15} />
              </svg>
              <p className="font-mono text-[0.65rem] sm:text-xs text-[var(--accent-cyan)] tracking-[0.3em] text-center animate-pulse">
                INITIALIZE EXPERIENCE
              </p>
            </div>
          </div>

          {/* Header */}
          <header
            className="absolute top-0 left-0 right-0 z-30 px-5 sm:px-8 py-4 sm:py-5 flex items-center justify-between transition-all duration-700"
            style={{
              opacity: isScrolling ? 0 : 1,
              pointerEvents: isScrolling ? "none" : "auto",
            }}
          >
            <div className="flex items-center gap-3">
              <svg viewBox="0 0 28 28" className="w-6 h-6 sm:w-7 sm:h-7">
                <circle cx="14" cy="14" r="12" stroke="var(--accent-cyan)" strokeWidth="1.5" fill="none" />
                <circle cx="14" cy="14" r="4" fill="var(--accent-cyan)" opacity={0.12} />
                <line x1="14" y1="8" x2="14" y2="20" stroke="var(--accent-cyan)" strokeWidth="0.75" opacity={0.4} />
                <line x1="8" y1="14" x2="20" y2="14" stroke="var(--accent-cyan)" strokeWidth="0.75" opacity={0.4} />
              </svg>
              <span className="font-mono text-[0.6rem] sm:text-[0.7rem] tracking-[0.25em] text-[var(--text-secondary)]">
                EXAMGUARD
              </span>
            </div>
            <a
              href="/dashboard"
              className="eg-focusable font-mono text-[0.6rem] sm:text-[0.7rem] tracking-wider text-[var(--text-tertiary)] hover:text-[var(--accent-cyan)] transition-colors duration-300"
            >
              DASHBOARD →
            </a>
          </header>

          {/* Fixed title — continuous scroll-driven motion */}
          <div className="absolute inset-x-0 top-[15%] sm:top-[18%] z-20 px-5 sm:px-8 pointer-events-none">
            <div
              className="transition-transform duration-200"
              style={{
                transform: `translateY(${-scrollState.progress * 80}vh)`,
              }}
            >
              <div className="mb-4 sm:mb-6">
                <p
                  className="font-mono text-[0.55rem] sm:text-[0.65rem] tracking-[0.4em] uppercase mb-3 sm:mb-4 transition-colors duration-500"
                  style={{ color: stage === "authorize" ? "var(--accent-emerald)" : "var(--accent-cyan)" }}
                >
                  {stage === "ready" ? "SCROLL TO BEGIN" : `0${scrollState.stageIndex} / ${titleText.split(" ")[0]}`}
                </p>
                <h1
                  className="font-display text-[2rem] sm:text-[3rem] md:text-[4rem] lg:text-[5rem] font-bold leading-[1.05] tracking-tight"
                  style={{ color: stage === "authorize" ? "var(--accent-emerald)" : "var(--text-primary)" }}
                >
                  {titleText}
                </h1>
              </div>
              <p className="font-mono text-[0.6rem] sm:text-xs text-[var(--text-tertiary)] tracking-wide max-w-md">
                {titleSubtext}
              </p>
            </div>
          </div>

          {/* Stage nav */}
          <div
            className="absolute top-4 sm:top-5 left-1/2 -translate-x-1/2 z-30 transition-opacity duration-500"
            style={{ opacity: isScrolling ? 1 : 0, pointerEvents: isScrolling ? "auto" : "none" }}
          >
            <StageNav stage={scrollState.stage} onStageClick={() => {}} />
          </div>

          {/* Left — Scene panel */}
          <div className="absolute right-4 sm:right-8 lg:right-12 top-1/2 -translate-y-1/2 z-10 w-[340px] sm:w-[420px] h-[440px] sm:h-[520px] pointer-events-none">
            <div
              className="relative w-full h-full eg-panel overflow-hidden"
              style={{
                opacity: interpolate(0, 1),
              }}
            >
              <svg className="absolute inset-0 w-full h-full" style={{ zIndex: 0 }}>
                <rect x="0" y="0" width="100%" height="100%" fill="none" stroke="var(--accent-cyan)" strokeWidth="0.5" strokeDasharray="4 4" opacity={0.08 + scrollState.progress * 0.12} style={{ transition: "opacity 0.4s" }} />
              </svg>

              <div className="relative z-10 p-5 sm:p-7 h-full flex flex-col">
                {/* Active stage title */}
                <div className="mb-3 sm:mb-5">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-mono text-[0.55rem] sm:text-[0.6rem] tracking-wider text-[var(--accent-cyan)]">
                      0{scrollState.stageIndex + 1}
                    </span>
                    <span className="font-mono text-[0.55rem] sm:text-[0.6rem] tracking-wider text-[var(--text-tertiary)] uppercase">
                      {stage === "ready" ? "SYSTEM" : stage}
                    </span>
                  </div>
                  <div className="h-px bg-[var(--border-subtle)]" />
                </div>

                {/* Evidence collection */}
                {scrollState.progress > 0.05 && (
                  <div className="space-y-2 sm:space-y-2.5 mb-4 sm:mb-6">
                    {[
                      { label: "LIVENESS", value: stage === "ready" ? "—" : "CHECK", active: stage === "detect" },
                      { label: "FACE", value: stage === "ready" ? "—" : "1:N", active: stage === "verify" },
                      { label: "EVIDENCE", value: stage === "ready" ? "—" : "COLLECT", active: stage === "decide" },
                      { label: "DECISION", value: stage === "ready" ? "—" : "ALLOW/DENY", active: stage === "authorize" },
                    ].map((item, i) => (
                      <div
                        key={item.label}
                        className="flex items-center gap-2 sm:gap-2.5 group"
                        style={{ opacity: scrollState.progress > 0.05 + i * 0.02 ? 1 : 0, transition: "opacity 0.3s" }}
                      >
                        <div className={`w-1 h-1 rounded-full ${item.active ? "bg-[var(--accent-cyan)]" : "bg-[var(--text-tertiary)] opacity-30"}`} />
                        <span className="font-mono text-[0.55rem] sm:text-[0.6rem] tracking-wider text-[var(--text-tertiary)] w-16 sm:w-20">
                          {item.label}
                        </span>
                        <span className={`font-mono text-[0.55rem] sm:text-[0.6rem] tracking-wider ${item.active ? "text-[var(--accent-cyan)]" : "text-[var(--text-tertiary)] opacity-40"}`}>
                          {item.value}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Center graphic */}
                <div className="flex-1 relative flex items-center justify-center">
                  {(stage === "ready" || stage === "detect") && (
                    <div style={{ opacity: stage === "ready" ? interpolate(0.8, 1) : detectOpacity, transition: "opacity 0.1s" }}>
                      <FaceGeometry phase={stage === "ready" ? "frame" : "connect"} parallaxStrength={0.02} />
                    </div>
                  )}
                  {stage === "verify" && (
                    <div style={{ opacity: verifyOpacity, transition: "opacity 0.1s" }}>
                      <HallTicketViz stage={stage} progress={scrollState.progress} subProgress={scrollState.subProgress} />
                    </div>
                  )}
                  {stage === "decide" && (
                    <div style={{ opacity: decideOpacity, transition: "opacity 0.1s" }}>
                      <FaceGeometry phase="evidence" parallaxStrength={0.02} />
                    </div>
                  )}
                  {stage === "authorize" && (
                    <div style={{ opacity: authorizeOpacity, transition: "opacity 0.1s" }}>
                      <FaceGeometry phase="authorize" parallaxStrength={0.02} />
                    </div>
                  )}
                </div>

                {/* Bottom status */}
                <div className="flex items-center justify-between mt-3 sm:mt-5">
                  <div className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${stage === "authorize" ? "bg-[var(--accent-emerald)]" : "bg-[var(--accent-cyan)]"} ${scrollState.progress > 0.05 ? "animate-pulse" : ""}`} />
                    <span className="font-mono text-[0.5rem] sm:text-[0.55rem] tracking-wider text-[var(--text-tertiary)]">
                      {stage === "ready" ? "STANDBY" : stage === "authorize" ? "VERIFIED" : "ACTIVE"}
                    </span>
                  </div>
                  <span className="font-mono text-[0.5rem] sm:text-[0.55rem] text-[var(--text-tertiary)] opacity-40">
                    {Math.round(scrollState.progress * 100)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right — Terminal panel */}
          <div className="absolute right-4 sm:right-8 lg:right-12 bottom-6 sm:bottom-8 z-20 w-[320px] sm:w-[400px] pointer-events-none">
            <SystemTerminal stage={scrollState.stage} subProgress={scrollState.subProgress} />
          </div>

          {/* Scroll hint */}
          {!initialized && (
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center gap-2 animate-bounce" style={{ animationDuration: "2.5s" }}>
              <div className="w-px h-8 bg-gradient-to-b from-transparent to-[var(--accent-cyan)] opacity-40" />
              <span className="font-mono text-[0.5rem] tracking-[0.3em] text-[var(--text-tertiary)]">SCROLL</span>
            </div>
          )}
        </div>
      </div>

      {/* SECTION 1: System Overview — below scroll experience */}
      <section className="relative bg-[var(--bg-surface)] border-t border-[var(--border-subtle)]">
        <div className="max-w-5xl mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <div className="text-center mb-14 sm:mb-20">
            <p className="font-mono text-[0.6rem] sm:text-[0.7rem] tracking-[0.35em] text-[var(--accent-cyan)] uppercase mb-3">
              THE PROBLEM
            </p>
            <h2 className="font-display text-[1.6rem] sm:text-[2.2rem] md:text-[2.8rem] font-bold text-[var(--text-primary)] leading-tight">
              Proxy attendance is an<br className="hidden sm:block" /> institutional crisis
            </h2>
            <p className="font-body text-sm sm:text-base text-[var(--text-tertiary)] mt-4 max-w-xl mx-auto leading-relaxed">
              At-scale cheating undermines examination integrity. Manual verification cannot scale.
              AI without accountability creates new risks.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
            {[
              { num: "01", title: "Identity Verification", desc: "Enrollment-time biometric binding. 1:N matching. Anti-spoofing liveness detection.", color: "var(--accent-cyan)" },
              { num: "02", title: "Proxy Detection", desc: "Multi-factor confidence scoring. Evidence-based decisions. Human override required.", color: "var(--accent-emerald)" },
              { num: "03", title: "Exam Security", desc: "Hall-ticket integrity. Seat assignment validation. Time-window enforcement.", color: "var(--accent-amber)" },
              { num: "04", title: "Admin Control", desc: "Manual override always available. Full audit trail. Institution-configurable thresholds.", color: "var(--accent-rose)" },
            ].map((item) => (
              <div key={item.num} className="eg-card group hover:border-[rgba(0,229,255,0.15)] transition-all duration-300">
                <span className="eg-label font-mono text-[0.55rem] sm:text-[0.6rem] tracking-wider" style={{ color: item.color }}>
                  {item.num}
                </span>
                <h3 className="font-display text-sm sm:text-base font-semibold text-[var(--text-primary)] mb-2 group-hover:text-[var(--accent-cyan)] transition-colors duration-300">
                  {item.title}
                </h3>
                <p className="font-body text-[0.75rem] sm:text-xs text-[var(--text-tertiary)] leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 2: Architecture */}
      <section className="relative bg-[var(--bg-base)]">
        <div className="max-w-4xl mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 sm:gap-16 items-start">
            <div>
              <p className="font-mono text-[0.6rem] sm:text-[0.7rem] tracking-[0.35em] text-[var(--accent-emerald)] uppercase mb-3">
                ARCHITECTURE
              </p>
              <h2 className="font-display text-[1.4rem] sm:text-[1.8rem] md:text-[2.2rem] font-bold text-[var(--text-primary)] leading-tight mb-5">
                AI as perception.<br />Not authority.
              </h2>
              <p className="font-body text-sm sm:text-base text-[var(--text-tertiary)] leading-relaxed mb-8 max-w-lg">
                ExamGuard separates what the AI sees from what the system decides.
                Provider output is evidence — never a direct authorization decision.
                The decision engine evaluates evidence against configurable thresholds.
                Human override is always available.
              </p>
              <div className="space-y-3">
                {["Provider-agnostic integration", "Evidence ≠ decision", "Configurable thresholds", "Full audit trail"].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-1 h-1 rounded-full bg-[var(--accent-emerald)]" />
                    <span className="font-mono text-[0.65rem] sm:text-[0.7rem] text-[var(--text-secondary)]">{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              {[
                { label: "ENTRY", color: "var(--accent-cyan)" },
                { label: "LIVENESS", color: "var(--accent-emerald)" },
                { label: "DECISION", color: "var(--accent-amber)" },
                { label: "AUDIT", color: "var(--accent-rose)" },
              ].map((layer, i) => (
                <div
                  key={layer.label}
                  className="eg-card group"
                  style={{
                    borderColor: activeFeature === i ? layer.color : undefined,
                    transition: "border-color 0.4s, box-shadow 0.4s",
                    boxShadow: activeFeature === i ? `0 0 20px ${layer.color}10` : undefined,
                  }}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full transition-colors duration-300" style={{ backgroundColor: activeFeature === i ? layer.color : "var(--text-tertiary)" }} />
                    <span className="font-mono text-[0.65rem] sm:text-[0.7rem] tracking-wider" style={{ color: activeFeature === i ? layer.color : "var(--text-secondary)" }}>
                      {layer.label}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 3: Principles */}
      <section className="relative bg-[var(--bg-surface)] border-t border-[var(--border-subtle)]">
        <div className="max-w-5xl mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <div className="text-center mb-12 sm:mb-16">
            <p className="font-mono text-[0.6rem] sm:text-[0.7rem] tracking-[0.35em] text-[var(--accent-amber)] uppercase mb-3">
              PRINCIPLES
            </p>
            <h2 className="font-display text-[1.4rem] sm:text-[1.8rem] md:text-[2.2rem] font-bold text-[var(--text-primary)]">
              Built on constraints
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
            {[
              { num: "01", title: "Student Privacy First", desc: "Minimal data collection. No biometric storage beyond enrollment hashes. Right to deletion." },
              { num: "02", title: "No Black-Box AI", desc: "Every AI decision is explainable. Evidence is logged. Thresholds are configurable." },
              { num: "03", title: "Human Override", desc: "AI assists. Humans decide. Manual override is always available with justification." },
              { num: "04", title: "Provider Independence", desc: "Swap face recognition providers without code changes. Evidence format is standardized." },
            ].map((item) => (
              <div key={item.num} className="eg-card group">
                <span className="eg-label font-mono text-[0.55rem] sm:text-[0.6rem] tracking-wider text-[var(--accent-amber)]">
                  {item.num}
                </span>
                <h3 className="font-display text-sm sm:text-base font-semibold text-[var(--text-primary)] mb-2 group-hover:text-[var(--accent-amber)] transition-colors duration-300">
                  {item.title}
                </h3>
                <p className="font-body text-[0.75rem] sm:text-xs text-[var(--text-tertiary)] leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 4: Timeline */}
      <section className="relative bg-[var(--bg-base)]">
        <div className="max-w-3xl mx-auto px-5 sm:px-8 py-20 sm:py-28">
          <div className="text-center mb-12 sm:mb-16">
            <p className="font-mono text-[0.6rem] sm:text-[0.7rem] tracking-[0.35em] text-[var(--accent-rose)] uppercase mb-3">
              DEVELOPMENT
            </p>
            <h2 className="font-display text-[1.4rem] sm:text-[1.8rem] md:text-[2.2rem] font-bold text-[var(--text-primary)]">
              23-phase build
            </h2>
          </div>
          <div className="space-y-3">
            {[
              { phase: "00-06", title: "Foundation", desc: "Models, schemas, config, admin CRUD, tests", status: "complete" },
              { phase: "07", title: "Identity Verification", desc: "Core verification engine with provider abstraction", status: "complete" },
              { phase: "08", title: "UniFace Integration", desc: "Face recognition provider + anti-proxy + attendance", status: "upcoming" },
              { phase: "09-14", title: "Hall Tickets & Exams", desc: "Ticket generation, seat assignment, exam lifecycle", status: "upcoming" },
              { phase: "15-18", title: "Monitoring & Analytics", desc: "Real-time monitoring, alerts, analytics", status: "upcoming" },
              { phase: "19-23", title: "Auth & Polish", desc: "Authentication, RBAC, performance, deployment", status: "upcoming" },
            ].map((item) => (
              <div key={item.phase} className={`eg-card ${item.status === "complete" ? "border-[rgba(0,229,255,0.12)]" : ""}`}>
                <div className="flex items-start gap-4">
                  <span className="font-mono text-[0.6rem] sm:text-[0.65rem] tracking-wider text-[var(--text-tertiary)] w-12 flex-shrink-0 pt-0.5">
                    {item.phase}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-display text-sm font-semibold text-[var(--text-primary)]">
                        {item.title}
                      </h3>
                      {item.status === "complete" && (
                        <span className="font-mono text-[0.5rem] tracking-wider text-[var(--accent-emerald)] bg-[rgba(16,185,129,0.08)] px-1.5 py-0.5 rounded">
                          DONE
                        </span>
                      )}
                    </div>
                    <p className="font-body text-[0.7rem] sm:text-xs text-[var(--text-tertiary)] mt-1">
                      {item.desc}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[var(--bg-surface)] border-t border-[var(--border-subtle)]">
        <div className="max-w-5xl mx-auto px-5 sm:px-8 py-12 sm:py-16">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8 sm:gap-10">
            <div className="col-span-2 sm:col-span-1">
              <div className="flex items-center gap-2 mb-3">
                <svg viewBox="0 0 28 28" className="w-5 h-5">
                  <circle cx="14" cy="14" r="12" stroke="var(--accent-cyan)" strokeWidth="1.5" fill="none" />
                  <circle cx="14" cy="14" r="4" fill="var(--accent-cyan)" opacity={0.15} />
                </svg>
                <span className="font-mono text-[0.65rem] tracking-[0.2em] text-[var(--text-secondary)]">EXAMGUARD</span>
              </div>
              <p className="font-body text-[0.7rem] sm:text-xs text-[var(--text-tertiary)] leading-relaxed">
                AI-powered examination verification. Built for institutions that take integrity seriously.
              </p>
            </div>
            <div>
              <h4 className="font-mono text-[0.6rem] sm:text-[0.65rem] tracking-[0.2em] text-[var(--text-secondary)] mb-3">SYSTEM</h4>
              <ul className="space-y-2">
                {["Identity Verification", "Exam Security", "Admin Dashboard", "API Documentation"].map((item) => (
                  <li key={item}>
                    <span className="font-body text-[0.7rem] sm:text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors duration-300 cursor-pointer">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-mono text-[0.6rem] sm:text-[0.65rem] tracking-[0.2em] text-[var(--text-secondary)] mb-3">COMPLIANCE</h4>
              <ul className="space-y-2">
                {["Privacy Policy", "Terms of Service", "Data Processing", "Security"].map((item) => (
                  <li key={item}>
                    <span className="font-body text-[0.7rem] sm:text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors duration-300 cursor-pointer">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-mono text-[0.6rem] sm:text-[0.65rem] tracking-[0.2em] text-[var(--text-secondary)] mb-3">STATUS</h4>
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-emerald)] animate-pulse" />
                  <span className="font-mono text-[0.55rem] sm:text-[0.6rem] text-[var(--text-tertiary)]">All systems operational</span>
                </div>
                <div className="font-mono text-[0.55rem] sm:text-[0.6rem] text-[var(--text-tertiary)] opacity-60">
                  v0.7.0 — Identity Verification
                </div>
              </div>
            </div>
          </div>
          <div className="mt-10 sm:mt-14 pt-6 sm:pt-8 border-t border-[var(--border-subtle)]">
            <p className="font-mono text-[0.55rem] sm:text-[0.6rem] text-[var(--text-tertiary)] opacity-50 text-center tracking-wider">
              EXAMGUARD — AI-POWERED EXAMINATION INTEGRITY PLATFORM
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
