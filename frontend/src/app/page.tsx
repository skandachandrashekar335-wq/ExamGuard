"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { useScrollProgress, useMouseCSS, type ScrollState } from "@/components/useScrollProgress";
import FaceGeometry from "@/components/FaceGeometry";
import HallTicketViz from "@/components/HallTicketViz";
import StageNav from "@/components/StageNav";
import SystemTerminal from "@/components/SystemTerminal";

const STAGE_STARTS = [0, 0.05, 0.3, 0.55, 0.8];

export default function Home() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { subscribe, getState } = useScrollProgress(scrollRef);
  useMouseCSS();

  const [scrollState, setScrollState] = useState<ScrollState>(() => getState());
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    return subscribe(setScrollState);
  }, [subscribe]);

  useEffect(() => {
    if (!initialized && scrollState.progress > 0.01) {
      setInitialized(true);
    }
  }, [scrollState.progress, initialized]);

  const handleStageClick = useCallback((stageIndex: number) => {
    const el = scrollRef.current;
    if (!el) return;
    const target = STAGE_STARTS[stageIndex] || 0;
    const rect = el.getBoundingClientRect();
    const total = rect.height - window.innerHeight;
    const y = el.getBoundingClientRect().top + window.scrollY + total * target;
    window.scrollTo({ top: y, behavior: "auto" });
  }, []);

  const { stage, subProgress, progress, stageIndex } = scrollState;
  const isScrolling = progress > 0.01;

  const opacity = (start: number, peak: number, end: number) => {
    if (progress < start || progress > end) return 0;
    return progress < peak
      ? Math.max(0, Math.min(1, (progress - start) / (peak - start)))
      : Math.max(0, Math.min(1, (end - progress) / (end - peak)));
  };

  const detectOpacity = opacity(0.05, 0.12, 0.28);
  const verifyOpacity = opacity(0.3, 0.37, 0.53);
  const decideOpacity = opacity(0.55, 0.62, 0.78);
  const authorizeOpacity = opacity(0.8, 0.87, 1.0);

  const stageTitle =
    stage === "ready" ? "ENTRY SHOULD BE\nVERIFIED."
    : stage === "detect" ? "DETECTION STAGE"
    : stage === "verify" ? "IDENTITY + CONTEXT"
    : stage === "decide" ? "EVIDENCE ≠ DECISION"
    : "ENTRY DECISION\nREQUIRED.";

  const stageSubtext =
    stage === "ready" ? "Scroll to begin the verification experience"
    : stage === "detect" ? "Facial liveness and anti-spoofing detection"
    : stage === "verify" ? "Hall-ticket context meets identity verification"
    : stage === "decide" ? "AI perception informs — does not decide"
    : "Awaiting verified decision from evidence engine.";

  return (
    <>
      <div ref={scrollRef} style={{ height: "500vh" }} className="relative">
        <div className="eg-sticky overflow-hidden">

          {/* Power-up overlay */}
          <div
            className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[var(--bg-base)] transition-opacity duration-500"
            style={{ opacity: initialized ? 0 : 1, pointerEvents: initialized ? "none" : "auto" }}
          >
            <div className="text-center">
              <p className="eg-mono text-[var(--gray-500)] mb-3">INITIALIZE</p>
              <div className="w-8 h-px bg-[var(--gray-700)] mx-auto" />
            </div>
          </div>

          {/* Header */}
          <header
            className="absolute top-0 left-0 right-0 z-30 px-6 sm:px-10 py-5 flex items-center justify-between transition-opacity duration-500"
            style={{ opacity: isScrolling ? 0 : 1, pointerEvents: isScrolling ? "none" : "auto" }}
          >
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 border border-[var(--gray-400)] rotate-45" />
              <span className="eg-mono-sm text-[var(--gray-500)]">EXAMGUARD</span>
            </div>
            <a
              href="/dashboard"
              className="eg-focusable eg-mono-sm text-[var(--gray-500)] hover:text-[var(--white)] transition-colors duration-200"
            >
              DASHBOARD →
            </a>
          </header>

          {/* Title — scroll-driven motion */}
          <div className="absolute inset-x-0 top-[12%] sm:top-[15%] z-20 px-6 sm:px-10 pointer-events-none">
            <div
              className="transition-transform duration-100"
              style={{ transform: `translateY(${-progress * 80}vh)` }}
            >
              <p className="eg-mono-sm text-[var(--gray-500)] mb-4">
                {stage === "ready" ? "SCROLL TO BEGIN" : `0${stageIndex} / ${stage.toUpperCase()}`}
              </p>
              <h1
                className="eg-display-lg text-[2.5rem] sm:text-[4rem] md:text-[5.5rem] lg:text-[7rem] whitespace-pre-line"
                style={{ color: stage === "authorize" ? "var(--gray-300)" : "var(--white)" }}
              >
                {stageTitle}
              </h1>
              <p className="eg-body text-sm sm:text-base text-[var(--gray-500)] mt-4 max-w-md">
                {stageSubtext}
              </p>
            </div>
          </div>

          {/* Stage navigation */}
          <div
            className="absolute top-5 left-1/2 -translate-x-1/2 z-30 transition-opacity duration-300"
            style={{ opacity: isScrolling ? 1 : 0, pointerEvents: isScrolling ? "auto" : "none" }}
          >
            <StageNav stage={stage} onStageClick={handleStageClick} />
          </div>

          {/* Right panel — scene visualizer */}
          <div className="absolute right-6 sm:right-10 lg:right-16 top-1/2 -translate-y-1/2 z-10 w-[300px] sm:w-[380px] h-[400px] sm:h-[480px] pointer-events-none">
            <div
              className="relative w-full h-full border border-[var(--border)] bg-[var(--bg-surface)]"
              style={{ opacity: subProgress === 0 && stage === "ready" ? 0.8 : 1 }}
            >
              {/* Stage label */}
              <div className="absolute top-0 left-0 px-3 py-2">
                <span className="eg-mono-sm text-[var(--gray-600)]">
                  {stage === "ready" ? "SYSTEM" : stage.toUpperCase()}
                </span>
              </div>

              {/* Visual area */}
              <div className="absolute inset-0 flex items-center justify-center p-8">
                {(stage === "ready" || stage === "detect") && (
                  <div style={{ opacity: stage === "ready" ? 0.8 : detectOpacity }} className="w-full h-full">
                    <FaceGeometry phase={stage === "ready" ? "frame" : "scan"} />
                  </div>
                )}
                {stage === "verify" && (
                  <div style={{ opacity: verifyOpacity }} className="w-full">
                    <HallTicketViz progress={progress} subProgress={subProgress} />
                  </div>
                )}
                {stage === "decide" && (
                  <div style={{ opacity: decideOpacity }} className="w-full h-full">
                    <FaceGeometry phase="evidence" />
                  </div>
                )}
                {stage === "authorize" && (
                  <div style={{ opacity: authorizeOpacity }} className="w-full h-full">
                    <FaceGeometry phase="authorize" />
                  </div>
                )}
              </div>

              {/* Status bar */}
              <div className="absolute bottom-0 left-0 right-0 px-3 py-2 flex items-center justify-between border-t border-[var(--border)]">
                <span className="eg-mono-sm text-[var(--gray-600)]">
                  {stage === "ready" ? "STANDBY" : "ACTIVE"}
                </span>
                <span className="eg-mono-sm text-[var(--gray-700)]">
                  {Math.round(progress * 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* Bottom — terminal */}
          <div className="absolute right-6 sm:right-10 lg:right-16 bottom-6 z-20 w-[280px] sm:w-[360px] pointer-events-none">
            <SystemTerminal stage={stage} />
          </div>

          {/* Scroll hint */}
          {!initialized && (
            <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20 flex flex-col items-center gap-2">
              <div className="w-px h-8 bg-[var(--gray-700)]" />
              <span className="eg-mono-sm text-[var(--gray-600)]">SCROLL</span>
            </div>
          )}
        </div>
      </div>

      {/* ============================
          SECTION 1 — THE PROBLEM
          ============================ */}
      <section className="bg-[var(--bg-surface)] border-t border-[var(--border)]">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="mb-16">
            <p className="eg-mono-sm text-[var(--gray-500)] mb-4">THE PROBLEM</p>
            <h2 className="eg-display text-[1.8rem] sm:text-[2.5rem] md:text-[3rem] max-w-2xl">
              Proxy attendance is an institutional crisis
            </h2>
            <p className="eg-body text-sm sm:text-base text-[var(--gray-400)] mt-5 max-w-xl">
              At-scale cheating undermines examination integrity.
              Manual verification cannot scale.
              AI without accountability creates new risks.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[var(--border)]">
            {[
              { num: "01", title: "Identity Verification", desc: "Enrollment-time biometric binding. 1:N matching. Anti-spoofing liveness detection." },
              { num: "02", title: "Proxy Detection", desc: "Multi-factor confidence scoring. Evidence-based decisions. Human override required." },
              { num: "03", title: "Exam Security", desc: "Hall-ticket integrity. Seat assignment validation. Time-window enforcement." },
              { num: "04", title: "Admin Control", desc: "Manual override always available. Full audit trail. Institution-configurable thresholds." },
            ].map((item) => (
              <div key={item.num} className="bg-[var(--bg-raised)] p-6 sm:p-8 group hover:bg-[var(--bg-base)] transition-colors duration-300">
                <span className="eg-mono-sm text-[var(--gray-600)] block mb-3">{item.num}</span>
                <h3 className="eg-display text-base sm:text-lg text-[var(--white)] mb-2">{item.title}</h3>
                <p className="eg-body text-xs sm:text-sm text-[var(--gray-400)]">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================
          SECTION 2 — ARCHITECTURE
          ============================ */}
      <section className="bg-[var(--bg-base)]">
        <div className="max-w-4xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20">
            <div>
              <p className="eg-mono-sm text-[var(--gray-500)] mb-4">ARCHITECTURE</p>
              <h2 className="eg-display text-[1.8rem] sm:text-[2.2rem] md:text-[2.8rem] leading-tight mb-5">
                AI as perception.
                <br />
                Not authority.
              </h2>
              <p className="eg-body text-sm sm:text-base text-[var(--gray-400)] mb-8 max-w-lg">
                ExamGuard separates what the AI sees from what the system decides.
                Provider output is evidence — never a direct authorization decision.
                The decision engine evaluates evidence against configurable thresholds.
                Human override is always available.
              </p>
              <div className="space-y-3">
                {["Provider-agnostic integration", "Evidence ≠ decision", "Configurable thresholds", "Full audit trail"].map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-1 h-px bg-[var(--gray-500)]" />
                    <span className="eg-mono-sm text-[var(--gray-400)]">{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-px bg-[var(--border)]">
              {[
                { label: "ENTRY", desc: "Hall ticket + student context" },
                { label: "LIVENESS", desc: "Anti-spoofing detection" },
                { label: "DECISION", desc: "Evidence threshold evaluation" },
                { label: "AUDIT", desc: "Full decision trail" },
              ].map((layer) => (
                <div key={layer.label} className="bg-[var(--bg-raised)] p-5 flex items-start gap-4">
                  <span className="eg-mono-sm text-[var(--gray-500)] w-16 flex-shrink-0">{layer.label}</span>
                  <span className="eg-body text-sm text-[var(--gray-400)]">{layer.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============================
          SECTION 3 — PRINCIPLES
          ============================ */}
      <section className="bg-[var(--bg-surface)] border-t border-[var(--border)]">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="mb-12">
            <p className="eg-mono-sm text-[var(--gray-500)] mb-4">PRINCIPLES</p>
            <h2 className="eg-display text-[1.8rem] sm:text-[2.2rem]">Built on constraints</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[var(--border)]">
            {[
              { num: "01", title: "Student Privacy First", desc: "Minimal data collection. No biometric storage beyond enrollment hashes. Right to deletion." },
              { num: "02", title: "No Black-Box AI", desc: "Every AI decision is explainable. Evidence is logged. Thresholds are configurable." },
              { num: "03", title: "Human Override", desc: "AI assists. Humans decide. Manual override is always available with justification." },
              { num: "04", title: "Provider Independence", desc: "Swap face recognition providers without code changes. Evidence format is standardized." },
            ].map((item) => (
              <div key={item.num} className="bg-[var(--bg-raised)] p-6 sm:p-8">
                <span className="eg-mono-sm text-[var(--gray-600)] block mb-3">{item.num}</span>
                <h3 className="eg-display text-base sm:text-lg text-[var(--white)] mb-2">{item.title}</h3>
                <p className="eg-body text-xs sm:text-sm text-[var(--gray-400)]">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================
          SECTION 4 — ROADMAP
          ============================ */}
      <section className="bg-[var(--bg-base)]">
        <div className="max-w-3xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="mb-12">
            <p className="eg-mono-sm text-[var(--gray-500)] mb-4">DEVELOPMENT</p>
            <h2 className="eg-display text-[1.8rem] sm:text-[2.2rem]">23-phase build</h2>
          </div>
          <div className="space-y-px bg-[var(--border)]">
            {[
              { phase: "00–06", title: "Foundation", desc: "Models, schemas, config, admin CRUD, tests", done: true },
              { phase: "07", title: "Identity Verification", desc: "Core verification engine with provider abstraction", done: true },
              { phase: "08", title: "UniFace Integration", desc: "Face recognition provider + anti-proxy + attendance", done: false },
              { phase: "09–14", title: "Hall Tickets & Exams", desc: "Ticket generation, seat assignment, exam lifecycle", done: false },
              { phase: "15–18", title: "Monitoring & Analytics", desc: "Real-time monitoring, alerts, analytics", done: false },
              { phase: "19–23", title: "Auth & Polish", desc: "Authentication, RBAC, performance, deployment", done: false },
            ].map((item) => (
              <div key={item.phase} className="bg-[var(--bg-raised)] p-5 flex items-start gap-5">
                <span className="eg-mono-sm text-[var(--gray-600)] w-12 flex-shrink-0">{item.phase}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="eg-display text-sm text-[var(--white)]">{item.title}</h3>
                    {item.done && (
                      <span className="eg-mono-sm text-[var(--gray-500)] border border-[var(--gray-700)] px-1.5 py-0.5">
                        DONE
                      </span>
                    )}
                  </div>
                  <p className="eg-body text-xs text-[var(--gray-500)] mt-1">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================
          FOOTER
          ============================ */}
      <footer className="bg-[var(--bg-surface)] border-t border-[var(--border)]">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-12 sm:py-16">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
            <div className="col-span-2 sm:col-span-1">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 border border-[var(--gray-500)] rotate-45" />
                <span className="eg-mono-sm text-[var(--gray-500)]">EXAMGUARD</span>
              </div>
              <p className="eg-body text-xs text-[var(--gray-500)] leading-relaxed">
                AI-powered examination verification for institutions that take integrity seriously.
              </p>
            </div>
            <div>
              <h4 className="eg-mono-sm text-[var(--gray-500)] mb-3">SYSTEM</h4>
              <ul className="space-y-2">
                {[
                  { label: "Identity Verification", href: "/identity-verifications" },
                  { label: "Exam Security", href: "/exams" },
                  { label: "Admin Dashboard", href: "/dashboard" },
                ].map((item) => (
                  <li key={item.label}>
                    <a href={item.href} className="eg-body text-xs text-[var(--gray-500)] hover:text-[var(--white)] transition-colors duration-200">
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="eg-mono-sm text-[var(--gray-500)] mb-3">COMPLIANCE</h4>
              <ul className="space-y-2">
                {[
                  { label: "Privacy Policy", href: "/privacy" },
                  { label: "Terms of Service", href: "/terms" },
                ].map((item) => (
                  <li key={item.label}>
                    <a href={item.href} className="eg-body text-xs text-[var(--gray-500)] hover:text-[var(--white)] transition-colors duration-200">
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="eg-mono-sm text-[var(--gray-500)] mb-3">STATUS</h4>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-1 h-1 rounded-full bg-[var(--gray-500)]" />
                  <span className="eg-mono-sm text-[var(--gray-600)]">System operational</span>
                </div>
                <span className="eg-mono-sm text-[var(--gray-700)] block">v0.7.0</span>
              </div>
            </div>
          </div>
          <div className="mt-12 pt-6 border-t border-[var(--border)]">
            <p className="eg-mono-sm text-[var(--gray-700)] text-center">
              EXAMGUARD — AI-POWERED EXAMINATION INTEGRITY PLATFORM
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
