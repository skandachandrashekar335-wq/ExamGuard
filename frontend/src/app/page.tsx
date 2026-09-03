"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import FaceGeometry from "@/components/FaceGeometry";
import HallTicketViz from "@/components/HallTicketViz";
import SystemTerminal from "@/components/SystemTerminal";
import StageNav from "@/components/StageNav";
import { useScrollProgress } from "@/components/useScrollProgress";

type Stage = "ready" | "detect" | "verify" | "decide" | "authorize";

const STAGE_DATA: Record<Stage, { num: string; title: string; subtitle: string; systemLabel: string }> = {
  ready: { num: "", title: "READY", subtitle: "READY FOR VERIFICATION", systemLabel: "SYSTEM READY" },
  detect: { num: "01", title: "DETECT", subtitle: "DETECTION ACTIVE", systemLabel: "SCANNER ACTIVE" },
  verify: { num: "02", title: "VERIFY", subtitle: "AWAITING VERIFICATION INPUT", systemLabel: "VERIFICATION INPUT REQUIRED" },
  decide: { num: "03", title: "DECIDE", subtitle: "AWAITING EVIDENCE", systemLabel: "EVIDENCE ≠ DECISION" },
  authorize: { num: "04", title: "AUTHORIZE", subtitle: "AWAITING VERIFIED DECISION", systemLabel: "NO ENTRY WITHOUT DECISION" },
};

export default function Home() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { subscribe } = useScrollProgress(scrollRef);
  const [stage, setStage] = useState<Stage>("ready");
  const [progress, setProgress] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [navExpanded, setNavExpanded] = useState(false);

  useEffect(() => {
    return subscribe((state) => {
      setStage(state.stage);
      setProgress(state.progress);
    });
  }, [subscribe]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 2;
    const y = (e.clientY / window.innerHeight - 0.5) * 2;
    setMousePos({ x, y });
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [handleMouseMove]);

  const scrollToStage = (targetStage: string) => {
    const el = scrollRef.current;
    if (!el) return;
    const vh = window.innerHeight;
    const total = el.scrollHeight - vh;
    const stageTargets: Record<string, number> = {
      detect: 0.15,
      verify: 0.4,
      decide: 0.65,
      authorize: 0.9,
    };
    const target = stageTargets[targetStage] || 0;
    window.scrollTo({ top: total * target + el.offsetTop, behavior: "smooth" });
  };

  const currentData = STAGE_DATA[stage];

  return (
    <div className="bg-[var(--background)] text-[var(--foreground)]">
      {/* Fixed scan line */}
      <div className="eg-scan-line" />

      {/* Fixed stage nav */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-[rgba(5,5,5,0.85)] backdrop-blur-md border-b border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="eg-focusable">
              <span className="font-bold text-sm tracking-[0.15em] uppercase">ExamGuard</span>
            </Link>
            <span className="text-[var(--text-tertiary)] text-xs hidden sm:inline">|</span>
            <span className="eg-label hidden sm:inline">{currentData.systemLabel}</span>
          </div>
          <div className="hidden md:block">
            <StageNav stage={stage} onStageClick={scrollToStage} />
          </div>
          <button
            onClick={() => setNavExpanded(!navExpanded)}
            className="md:hidden eg-focusable p-2 text-[var(--text-secondary)]"
            aria-label="Toggle navigation"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 6h14M3 10h14M3 14h14" />
            </svg>
          </button>
        </div>
        {navExpanded && (
          <div className="md:hidden px-4 pb-3 border-t border-[var(--border)]">
            <div className="flex flex-col gap-1 pt-2">
              {(["detect", "verify", "decide", "authorize"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => { scrollToStage(s); setNavExpanded(false); }}
                  className={`eg-focusable text-left px-3 py-2 rounded text-xs font-mono ${
                    stage === s ? "text-[var(--accent-cyan)] bg-[rgba(0,229,255,0.1)]" : "text-[var(--text-tertiary)] hover:bg-white/5"
                  }`}
                >
                  {STAGE_DATA[s].num} {STAGE_DATA[s].title}
                </button>
              ))}
              <div className="border-t border-[var(--border)] mt-1 pt-1">
                <Link href="/dashboard" className="eg-focusable block px-3 py-2 rounded text-xs text-[var(--text-secondary)] hover:bg-white/5">
                  Dashboard
                </Link>
                <Link href="/students" className="eg-focusable block px-3 py-2 rounded text-xs text-[var(--text-secondary)] hover:bg-white/5">
                  Students
                </Link>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Scroll container */}
      <div ref={scrollRef} className="relative" style={{ height: "500vh" }}>

        {/* PINNED STAGE */}
        <div className="sticky top-0 h-screen overflow-hidden">
          <div className="absolute inset-0 eg-grid" />

          {/* Progress bar */}
          <div className="absolute top-0 left-0 right-0 h-[2px] z-10">
            <div
              className="h-full bg-gradient-to-r from-[var(--accent-cyan)] to-[var(--accent-emerald)]"
              style={{ width: `${progress * 100}%`, transition: "width 0.1s linear" }}
            />
          </div>

          {/* Desktop stage nav */}
          <div className="hidden md:block absolute top-20 left-0 right-0 z-10">
            <div className="max-w-7xl mx-auto px-6">
              <StageNav stage={stage} onStageClick={scrollToStage} />
            </div>
          </div>

          {/* Main content */}
          <div className="relative h-full flex flex-col lg:flex-row items-center justify-center max-w-7xl mx-auto px-4 sm:px-6 pt-24 pb-12">

            {/* Left — Text */}
            <div className="flex-1 lg:pr-8 mb-8 lg:mb-0 z-10 text-center lg:text-left">
              {stage === "ready" && (
                <div className="eg-fade-up">
                  <div className="eg-label mb-4">EXAMGUARD</div>
                  <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold uppercase tracking-wider leading-none mb-6">
                    VERIFY.
                    <br />
                    <span className="text-[var(--accent-cyan)]">THEN</span>
                    <br />
                    ENTER.
                  </h1>
                  <p className="text-[var(--text-secondary)] text-base sm:text-lg max-w-lg mx-auto lg:mx-0 mb-8 leading-relaxed">
                    Automated examination entry verification that connects
                    hall-ticket context with identity verification before
                    entry is authorized.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
                    <button
                      onClick={() => scrollToStage("detect")}
                      className="eg-btn-primary eg-focusable"
                    >
                      START EXPERIENCE
                    </button>
                    <Link href="/dashboard" className="eg-btn-secondary eg-focusable text-center">
                      EXPLORE SYSTEM
                    </Link>
                  </div>
                </div>
              )}

              {stage !== "ready" && (
                <div key={stage} className="eg-fade-up">
                  <div className="eg-label mb-3">
                    <span className="text-[var(--accent-cyan)]">{currentData.num}</span>
                    <span className="mx-2">/</span>
                    {currentData.title}
                  </div>
                  <h2 className="text-3xl sm:text-4xl lg:text-6xl font-bold uppercase tracking-wider leading-none mb-4">
                    {currentData.title}
                  </h2>
                  <p className="text-[var(--text-secondary)] text-sm sm:text-base max-w-md mx-auto lg:mx-0 mb-6">
                    {currentData.subtitle}
                  </p>

                  {stage === "verify" && (
                    <div className="eg-card max-w-md mx-auto lg:mx-0 mb-6">
                      <div className="eg-label text-[0.6rem] mb-2">ARCHITECTURE PRINCIPLE</div>
                      <div className="font-mono text-xs text-[var(--accent-cyan)]">
                        EVIDENCE ≠ DECISION
                      </div>
                      <p className="text-[var(--text-tertiary)] text-xs mt-2">
                        The verification provider provides evidence.
                        Business logic makes the authorization decision.
                      </p>
                    </div>
                  )}

                  {stage === "decide" && (
                    <div className="eg-card max-w-md mx-auto lg:mx-0 mb-6">
                      <div className="eg-label text-[0.6rem] mb-3">DECISION FLOW</div>
                      <div className="space-y-2 font-mono text-xs">
                        <div className="flex items-center gap-2">
                          <span className="text-[var(--accent-cyan)]">EVIDENCE</span>
                          <span className="text-[var(--text-tertiary)]">→</span>
                          <span className="text-[var(--accent-emerald)]">DECISION ENGINE</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[var(--accent-emerald)]">DECISION ENGINE</span>
                          <span className="text-[var(--text-tertiary)]">→</span>
                          <span className="text-[var(--accent-amber)]">AUTHORIZE / DENY</span>
                        </div>
                      </div>
                      <p className="text-[var(--text-tertiary)] text-xs mt-3">
                        No biometric data stored. No raw face images.
                        Configurable threshold evaluation.
                      </p>
                    </div>
                  )}

                  {stage === "authorize" && (
                    <div className="eg-card max-w-md mx-auto lg:mx-0 mb-6 border-[var(--accent-amber)]/30">
                      <div className="eg-label text-[0.6rem] mb-2 text-[var(--accent-amber)]">SYSTEM STATE</div>
                      <div className="font-mono text-sm text-[var(--accent-amber)]">
                        AWAITING VERIFIED DECISION
                      </div>
                      <p className="text-[var(--text-tertiary)] text-xs mt-2">
                        No entry is authorized without a verified decision.
                        The system does not auto-authorize.
                      </p>
                    </div>
                  )}

                  <div className="flex gap-3 justify-center lg:justify-start">
                    {stage !== "authorize" && (
                      <button
                        onClick={() => {
                          const next = ["detect", "verify", "decide", "authorize"];
                          const idx = next.indexOf(stage);
                          if (idx < next.length - 1) scrollToStage(next[idx + 1]);
                        }}
                        className="eg-btn-primary eg-focusable text-sm"
                      >
                        CONTINUE
                      </button>
                    )}
                    <Link href="/dashboard" className="eg-btn-secondary eg-focusable text-sm text-center">
                      DASHBOARD
                    </Link>
                  </div>
                </div>
              )}
            </div>

            {/* Right — Visual */}
            <div className="flex-1 lg:pl-8 flex flex-col items-center gap-6 z-10 max-w-lg w-full">
              <div className="w-full aspect-square max-w-[400px]">
                <FaceGeometry
                  stage={stage}
                  progress={progress}
                  mouseX={mousePos.x}
                  mouseY={mousePos.y}
                />
              </div>
              <div className="w-full">
                <HallTicketViz stage={stage} />
              </div>
            </div>
          </div>

          {/* Bottom — Terminal */}
          <div className="absolute bottom-0 left-0 right-0 px-4 sm:px-6 pb-4 max-w-7xl mx-auto">
            <SystemTerminal stage={stage} />
          </div>

          {/* Scroll hint */}
          {stage === "ready" && (
            <div className="absolute bottom-20 left-1/2 -translate-x-1/2 text-center z-10">
              <div className="eg-label text-[0.6rem] mb-2">SCROLL TO EXPLORE</div>
              <div className="w-5 h-8 border border-[var(--text-tertiary)] rounded-full mx-auto flex justify-center pt-1">
                <div className="w-1 h-2 bg-[var(--accent-cyan)] rounded-full animate-bounce" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* System Overview — after scroll experience */}
      <section className="eg-section eg-grid">
        <div className="max-w-6xl mx-auto">
          <div className="eg-label mb-4">SYSTEM OVERVIEW</div>
          <h2 className="text-3xl sm:text-4xl font-bold uppercase tracking-wider mb-4">
            FOUR STAGES
          </h2>
          <p className="text-[var(--text-secondary)] max-w-2xl mb-12">
            Each stage represents a real system state. The experience
            transforms as you scroll through the verification pipeline.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { num: "01", title: "DETECT", desc: "Scanner frame activates. Landmark nodes appear. Grid becomes visible." },
              { num: "02", title: "VERIFY", desc: "Identity and examination context are linked. Verification input required." },
              { num: "03", title: "DECIDE", desc: "Evidence converges. Decision engine evaluates. Evidence ≠ Decision." },
              { num: "04", title: "AUTHORIZE", desc: "Final security state. Awaiting verified decision. No auto-authorization." },
            ].map((s) => (
              <div key={s.num} className="eg-card group hover:border-[var(--accent-cyan)]/30 transition-colors duration-300">
                <div className="eg-label text-[var(--accent-cyan)] mb-3">{s.num}</div>
                <h3 className="text-lg font-bold uppercase tracking-wider mb-2">{s.title}</h3>
                <p className="text-[var(--text-tertiary)] text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture section */}
      <section className="eg-section">
        <div className="max-w-6xl mx-auto">
          <div className="eg-label mb-4">ARCHITECTURE</div>
          <h2 className="text-3xl sm:text-4xl font-bold uppercase tracking-wider mb-4">
            EVIDENCE ≠ DECISION
          </h2>
          <p className="text-[var(--text-secondary)] max-w-2xl mb-12">
            The provider must never directly authorize exam entry.
            Evidence is perception. Business logic is authority.
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="eg-card">
              <div className="eg-label text-[var(--accent-cyan)] mb-3">HALL-TICKET VALIDITY</div>
              <div className="space-y-2 font-mono text-xs text-[var(--text-secondary)]">
                <div>Document → OCR → Extraction</div>
                <div>Extraction → Matching</div>
                <div>Matching → VerificationOutcome</div>
              </div>
            </div>
            <div className="eg-card">
              <div className="eg-label text-[var(--accent-emerald)] mb-3">IDENTITY VERIFICATION</div>
              <div className="space-y-2 font-mono text-xs text-[var(--text-secondary)]">
                <div>Student → Exam Registration</div>
                <div>Registration → HallTicket</div>
                <div>HallTicket → IdentityVerificationAttempt</div>
                <div>Attempt → Evidence → Decision</div>
              </div>
            </div>
            <div className="eg-card">
              <div className="eg-label text-[var(--accent-amber)] mb-3">ENTRY AUTHORIZATION</div>
              <div className="space-y-2 font-mono text-xs text-[var(--text-secondary)]">
                <div>HallTicket Verified ✓</div>
                <div>Identity Verified ✓</div>
                <div>Decision Engine ✓</div>
                <div>→ Entry Authorized</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Quick access */}
      <section className="eg-section border-t border-[var(--border)]">
        <div className="max-w-6xl mx-auto">
          <div className="eg-label mb-6">SYSTEM ACCESS</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              { href: "/dashboard", label: "Dashboard" },
              { href: "/students", label: "Students" },
              { href: "/documents", label: "Documents" },
              { href: "/hall-tickets", label: "Hall Tickets" },
              { href: "/identity-verifications", label: "Identity Verifications" },
              { href: "/import", label: "Import" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="eg-card text-center hover:border-[var(--accent-cyan)]/30 transition-colors duration-300 eg-focusable"
              >
                <span className="text-sm font-medium">{link.label}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="eg-label">EXAMGUARD</div>
          <div className="flex gap-6">
            <Link href="/privacy" className="eg-focusable text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors">
              Privacy Policy
            </Link>
            <Link href="/terms" className="eg-focusable text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors">
              Terms & Conditions
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
