"use client";

import { useRef, useEffect, useState } from "react";
import FaceGeometry from "@/components/FaceGeometry";

export default function Home() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stage, setStage] = useState("ready");
  const [progress, setProgress] = useState(0);

  // Pipeline stages
  const stages = [
    { key: "CAMERA", title: "CAMERA", desc: "Stage 1 of 7" },
    { key: "IDENTITY", title: "IDENTITY", desc: "Stage 2 of 7" },
    { key: "LIVENESS", title: "LIVENESS", desc: "Stage 3 of 7" },
    { key: "HALL_TICKET", title: "HALL TICKET", desc: "Stage 4 of 7" },
    { key: "SEAT", title: "SEAT", desc: "Stage 5 of 7" },
    { key: "EVIDENCE", title: "EVIDENCE", desc: "Stage 6 of 7" },
    { key: "DECISION", title: "DECISION", desc: "Stage 7 of 7" },
  ];

  useEffect(() => {
    let animated = false;
    if (scrollRef.current && !animated) {
      animated = true;
      const observer = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting) {
            let current = 0;
            const interval = setInterval(() => {
              current += 10;
              setProgress(current);
              if (current >= 100) {
                clearInterval(interval);
                setProgress(100);
              }
            }, 20);
            setTimeout(() => observer.disconnect(), 1000);
          }
        },
        { root: scrollRef.current }
      );
      observer.observe(scrollRef.current);
    }
    return () => {
      if (scrollRef.current) {
        // observer will be cleaned up by React
      }
    };
  }, []);

  return (
    <>
      {/* Sticky Navigation */}
      <div className="sticky-nav">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 height-full flex items-center justify-between">
          <div className="flex items-center gap-2">
            <a href="/" className="eg-mono-sm font-medium uppercase tracking-wider">EXAMGUARD</a>
            <nav className="hidden sm:block sm:flex items-center gap-8">
              <a href="/examination-sessions" className="eg-mono-sm text-[#555555] hover:text-[#111111] transition-colors duration-200">PRODUCT</a>
              <a href="/identity-verifications" className="eg-mono-sm text-[#555555] hover:text-[#111111] transition-colors duration-200">VERIFICATION</a>
              <a href="/exams" className="eg-mono-sm text-[#555555] hover:text-[#111111] transition-colors duration-200">SECURITY</a>
              <a href="/monitoring" className="eg-mono-sm text-[#555555] hover:text-[#111111] transition-colors duration-200">ANALYTICS</a>
              <a href="/security-events" className="eg-mono-sm text-[#555555] hover:text-[#111111] transition-colors duration-200">AUDIT</a>
            </nav>
            <a href="/examination-sessions" className="eg-btn eg-btn-sm eg-btn-primary uppercase rounded-md px-3 text-xs">ACCESS SYSTEM</a>
          </div>
        </div>
      </div>

      {/* Hero Section */}
      <section className="relative min-h-[80vh] overflow-hidden bg-[var(--bg-light)]">
        <div className="max-w-7xl mx-auto px-6 py-12 sm:py-20">
          <div className="text-center">
            {/* Eyebrow */}
            <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-4">
              EXAM ENTRY / IDENTITY / SECURITY
            </p>

            {/* Main Headline */}
            <h1 className="eg-display font-bold text-[clamp(72px,10vw,200px)] text-[var(--black)] leading-[0.9] mb-6 capitalize">
              ENTRY SHOULD BE
              <span className="block">VERIFIED.</span>
            </h1>

            {/* Supporting Paragraph */}
            <p className="eg-body text-base text-[var(--gray-55)] max-w-xl mx-auto mb-12">
              An examination entry verification system connecting identity, hall-ticket, seating, evidence and attendance into one auditable workflow.
            </p>

            {/* Echo Stack + Verification Visual Container */}
            <div className="absolute inset-0 pointer-events-none">
              {/* Foreground text color */}
              <p className="eg-display text-[var(--black)] absolute inset-0 transform -translate-y-1/2 top-1/2 -translate-x-1/2 opacity-20 capitalize">ENTRY SHOULD BE VERIFIED.</p>

              {/* Background Echo Layers */}
              <div className="absolute inset-0 overflow-hidden">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-2 bg-[var(--gray-20)] opacity-30" />
                <div className="absolute top-1/4 left-1/3 -translate-x-1/3 -translate-y-1/4 w-16 h-1 bg-[var(--gray-30)] opacity-20" />
                <div className="absolute bottom-1/3 right-1/2 -translate-x-1/2 -translate-y-1/3 w-20 h-1 bg-[var(--gray-40)] opacity-20" />
              </div>

              {/* Scanning line */}
              <div className="absolute inset-0 overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-0.5 bg-[var(--primary)] animate-scan" />
              </div>
            </div>

            {/* Verification Visual */}
            <div className="relative z-10 pt-16">
              <div className="mx-auto w-24 h-24 rounded-full border-2 border-[var(--border)] flex items-center justify-center">
                <div className="w-3/4 h-3/4 rounded-full bg-[var(--gray-20)] relative">
                  <div className="absolute inset-0 animate-blink">
                    <div className="absolute top-0 left-0 w-full h-1 bg-[var(--gray-30)]" />
                    <div className="absolute bottom-0 right-0 w-full h-1 bg-[var(--gray-30)]" />
                  </div>
                  <span className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider absolute inset-0 flex items-center justify-center">
                    CAMERA
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Narrative Pipeline */}
      <section
        className="py-24 sm:py-32 bg-[var(--bg-light)] border-t border-[var(--border)]"
      >
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-4">
                VERIFICATION PIPELINE
              </p>
              <h2 className="eg-display text-[2rem] sm:text-[2.5rem] md:text-[3rem] mb-6">
                CAMERA → IDENTITY → LIVENESS → HALL TICKET → SEAT → EVIDENCE → DECISION
              </h2>
              <p className="eg-body text-sm sm:text-base text-[var(--gray-55)] leading-relaxed mb-8">
                The seven-stage pipeline that governs every examination entry. Each stage
                validates the evidence before progression. Human review remains available
                at every step.
              </p>
            </div>
            <div className="space-y-4">
              {stages.map((stage) => (
                <div
                  key={stage.key}
                  className="bg-[var(--bg-raised)] p-4 rounded border border-[var(--border)] transition-colors duration-300 hover:border-[var(--border-strong)]"
                >
                  <span className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider block mb-2">
                    {stage.key}
                  </span>
                  <p className="eg-body text-sm text-[var(--gray-400)]">{stage.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* AI Perception */}
      <section
        className="py-24 sm:py-32 bg-[var(--bg-light)] border-t border-[var(--border)]"
      >
        <div className="max-w-4xl mx-auto px-6 sm:px-10">
          <div className="text-center mb-12">
            <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-2">
              AI AS PERCEPTION
            </p>
            <h2 className="eg-display text-3xl sm:text-4xl md:text-5xl font-bold mb-4">
              AI <span className="text-[var(--gray-400)]">NOT</span> AUTHORITY
            </h2>
            <p className="eg-body text-base sm:text-lg text-[var(--gray-55)] leading-relaxed max-w-xl mx-auto">
              AI produces evidence. The system evaluates evidence. Human review remains
              possible. The decision engine evaluates evidence against configurable
              thresholds. Human override is always available.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-6 mt-12">
            <div className="bg-[var(--bg-raised)] p-6 rounded border border-[var(--border)]">
              <div className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-3">AI</div>
              <p className="eg-body text-sm text-[var(--gray-400)]">
                Perceives biometric data. Outputs evidence package.
              </p>
            </div>
            <div className="bg-[var(--bg-raised)] p-6 rounded border border-[var(--border)]">
              <div className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-3">EVidence</div>
              <p className="eg-body text-sm text-[var(--gray-400)]">
                Standardized format. Includes confidence metrics. No authorization claim.
              </p>
            </div>
            <div className="bg-[var(--bg-raised)] p-6 rounded border border-[var(--border)]">
              <div className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-3">DECISION ENGINE</div>
              <p className="eg-body text-sm text-[var(--gray-400)]">
                Evaluates evidence. Applies thresholds. Supports human override.
              </p>
            </div>
            <div className="bg-[var(--bg-raised)] p-6 rounded border border-[var(--border)]">
              <div className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-3">HUMAN REVIEW</div>
              <p className="eg-body text-sm text-[var(--gray-400)]">
                Always available. Can approve, reject, or request modification.
                Full audit trail maintained.
              </p>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-[var(--border)]">
            <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-3">
              Every decision leaves a trail
            </p>
            <a href="/examination-sessions" className="eg-btn eg-btn-primary uppercase tracking-wider">
              EXPLORE VERIFICATION FLOW
            </a>
          </div>
        </div>
      </section>

      {/* Live Verification */}
      <section
        className="py-24 sm:py-32 bg-[var(--bg-light)] border-t border-[var(--border)]"
      >
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="grid lg:grid-cols-2 gap-12">
            <div>
              <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-4">
                LIVE VERIFICATION
              </p>
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-[var(--bg-raised)] border border-[var(--border)] rounded p-4 text-center transition-colors duration-300">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.7rem] uppercase tracking-wider mb-2">ANALYZING</span>
                  <p className="eg-body text-sm text-[var(--gray-400)]">In progress</p>
                </div>
                <div className="bg-[var(--bg-raised)] border border-[var(--border)] rounded p-4 text-center transition-colors duration-300">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.7rem] uppercase tracking-wider mb-2">COLLECTING</span>
                  <p className="eg-body text-sm text-[var(--gray-400)]">In progress</p>
                </div>
                <div className="bg-[var(--bg-raised)] border border-[var(--border)] rounded p-4 text-center transition-colors duration-300">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.7rem] uppercase tracking-wider mb-2">VALIDATING</span>
                  <p className="eg-body text-sm text-[var(--gray-400)]">In progress</p>
                </div>
                <div className="bg-[var(--bg-raised)] border border-[var(--border)] rounded p-4 text-center transition-colors duration-300">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.7rem] uppercase tracking-wider mb-2">REVIEW REQUIRED</span>
                  <p className="eg-body text-sm text-[var(--gray-400)]">In progress</p>
                </div>
              </div>
              <div className="bg-[var(--bg-raised)] p-6 rounded border border-[var(--border)] mb-8">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="eg-mono text-[var(--gray-500)] text-xs uppercase tracking-wider block mb-2">EXAM SESSION</span>
                    <p className="eg-body text-sm text-[var(--gray-500)]">BCA — End Semester</p>
                  </div>
                  <div>
                    <span className="eg-mono text-[var(--gray-500)] text-xs uppercase tracking-wider block mb-2">ENTRY POINT</span>
                    <p className="eg-body text-sm text-[var(--gray-500)]">GATE 02</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="eg-mono text-[var(--gray-500)] text-xs uppercase tracking-wider block mb-2">HALL TICKET</span>
                    <p className="eg-body text-sm text-[var(--gray-500)]">VALIDATING</p>
                  </div>
                  <div>
                    <span className="eg-mono text-[var(--gray-500)] text-xs uppercase tracking-wider block mb-2">SEAT ASSIGNED</span>
                    <p className="eg-body text-sm text-[var(--gray-500)]">A-17</p>
                  </div>
                </div>
              </div>
            </div>
            <div>
              <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-4">
                RISK ASSESSMENT
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="security-signal">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">IDENTITY MISMATCH</span>
                  <span className="eg-body text-xs text-[var(--gray-400)]">Identity mismatch detected</span>
                </div>
                <div className="security-signal">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">WRONG HALL</span>
                  <span className="eg-body text-xs text-[var(--gray-400)]">Candidate assigned to wrong hall</span>
                </div>
                <div className="security-signal">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">LIVENESS SPOOF</span>
                  <span className="eg-body text-xs text-[var(--gray-400)]">Liveness spoof detected</span>
                </div>
                <div className="security-signal">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">WRONG ENTRY POINT</span>
                  <span className="eg-body text-xs text-[var(--gray-400)]">Candidate entered through wrong gate</span>
                </div>
                <div className="security-signal">
                  <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">REPEATED FAILED VERIFICATION</span>
                  <span className="eg-body text-xs text-[var(--gray-400)]">Multiple failed verification attempts</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Security Signals */}
      <section
        className="py-24 sm:py-32 bg-[var(--bg-light)] border-t border-[var(--border)]"
      >
        <div className="max-w-6xl mx-auto px-6 sm:px-10">
          <div className="text-center mb-12">
            <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-2">
              SECURITY SIGNALS
            </p>
            <h2 className="eg-display text-2xl sm:text-3xl font-semibold mb-4">
              Every decision is guarded
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="security-signal" style={{ borderLeftColor: "#000" }}>
              <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">IDENTITY MISMATCH</span>
              <span className="eg-body text-xs text-[var(--gray-400)]">Identity mismatch detected</span>
            </div>
            <div className="security-signal" style={{ borderLeftColor: "#000" }}>
              <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">WRONG HALL</span>
              <span className="eg-body text-xs text-[var(--gray-400)]">Candidate assigned to wrong hall</span>
            </div>
            <div className="security-signal" style={{ borderLeftColor: "#555555" }}>
              <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">LIVENESS SPOOF</span>
              <span className="eg-body text-xs text-[var(--gray-400)]">Liveness spoof detected</span>
            </div>
            <div className="security-signal" style={{ borderLeftColor: "#555555" }}>
              <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">WRONG ENTRY POINT</span>
              <span className="eg-body text-xs text-[var(--gray-400)]">Candidate entered through wrong gate</span>
            </div>
            <div className="security-signal" style={{ borderLeftColor: "#555555" }}>
              <span className="eg-mono text-[var(--gray-500)] text-[0.6rem] uppercase tracking-wider block mb-1">REPEATED FAILED VERIFICATION</span>
              <span className="eg-body text-xs text-[var(--gray-400)]">Multiple failed verification attempts</span>
            </div>
          </div>
        </div>
      </section>

      {/* Admin Product */}
      <section
        className="py-24 sm:py-32 bg-[var(--bg-light)] border-t border-[var(--border)]"
      >
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="text-center mb-12">
            <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-2">
              EXAMINATION INTEGRITY
            </p>
            <h2 className="eg-display text-2xl sm:text-3xl font-semibold mb-4">
              BUILT INTO EVERY ENTRY
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <a href="/dashboard" className="eg-btn eg-btn-sm eg-btn-primary uppercase tracking-wider">
              Dashboard
            </a>
            <a href="/exams" className="eg-btn eg-btn-sm uppercase tracking-wider text-[#555555] hover:#111111 transition-colors duration-200">
              Exams
            </a>
            <a href="/examination-sessions" className="eg-btn eg-btn-sm uppercase tracking-wider text-[#555555] hover:#111111 transition-colors duration-200">
              Sessions
            </a>
            <a href="/monitoring" className="eg-btn eg-btn-sm uppercase tracking-wider text-[#555555] hover:#111111 transition-colors duration-200">
              Monitoring
            </a>
            <a href="/security-events" className="eg-btn eg-btn-sm uppercase tracking-wider text-[#555555] hover:#111111 transition-colors duration-200">
              Security Events
            </a>
          </div>
          <p className="mt-8 eg-mono text-[#707070] text-xs uppercase tracking-wider">
            EXAMINATION INTEGRITY, BUILT INTO EVERY ENTRY.
          </p>
        </div>
      </section>

      {/* The Problem */}
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
                <h3 className="eg-display text-base sm:text-lg text-[#FFFFFF] mb-2">{item.title}</h3>
                <p className="eg-body text-xs sm:text-sm text-[#CCCCCC]">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section className="bg-[var(--bg-surface)]">
        <div className="max-w-4xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <p className="eg-mono text-[var(--gray-55)] text-xs uppercase tracking-wider mb-4">ARCHITECTURE</p>
              <h2 className="eg-display text-[1.8rem] sm:text-[2.2rem] md:text-[2.8rem] leading-tight mb-5">
                AI as perception.
                <br />
                Not authority.
              </h2>
              <p className="eg-body text-sm sm:text-base text-[#CCCCCC] mb-8 max-w-lg">
                ExamGuard separates what the AI sees from what the system decides.
                Provider output is evidence — never a direct authorization decision.
                The decision engine evaluates evidence against configurable thresholds.
                Human override is always available.
              </p>
              <div className="space-y-3">
                <div key="0" className="flex items-center gap-3">
                  <div className="w-1 h-px bg-[#777777]" />
                  <span className="eg-mono-sm text-[#777777]">Provider-agnostic integration</span>
                </div>
                <div key="1" className="flex items-center gap-3">
                  <div className="w-1 h-px bg-[#777777]" />
                  <span className="eg-mono-sm text-[#777777]">Evidence ≠ decision</span>
                </div>
                <div key="2" className="flex items-center gap-3">
                  <div className="w-1 h-px bg-[#777777]" />
                  <span className="eg-mono-sm text-[#777777]">Configurable thresholds</span>
                </div>
                <div key="3" className="flex items-center gap-3">
                  <div className="w-1 h-px bg-[#777777]" />
                  <span className="eg-mono-sm text-[#777777]">Full audit trail</span>
                </div>
              </div>
            </div>
            <div className="bg-[var(--bg-raised)] p-5 flex items-start gap-4">
              <span className="eg-mono-sm text-[#777777] w-16 flex-shrink-0">ENTRY</span>
              <span className="eg-body text-sm text-[#888888]">Hall ticket + student context</span>
            </div>
            <div className="bg-[var(--bg-raised)] p-5 flex items-start gap-4">
              <span className="eg-mono-sm text-[#777777] w-16 flex-shrink-0">LIVENESS</span>
              <span className="eg-body text-sm text-[#888888]">Anti-spoofing detection</span>
            </div>
            <div className="bg-[var(--bg-raised)] p-5 flex items-start gap-4">
              <span className="eg-mono-sm text-[#777777] w-16 flex-shrink-0">DECISION</span>
              <span className="eg-body text-sm text-[#888888]">Evidence threshold evaluation</span>
            </div>
            <div className="bg-[var(--bg-raised)] p-5 flex items-start gap-4">
              <span className="eg-mono-sm text-[#777777] w-16 flex-shrink-0">AUDIT</span>
              <span className="eg-body text-sm text-[#888888]">Full decision trail</span>
            </div>
          </div>
        </div>
      </section>

      {/* Principles */}
      <section className="bg-[var(--bg-surface)] border-t border-[var(--border)]">
        <div className="max-w-5xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="mb-12">
            <p className="eg-mono-sm text-[#777777] mb-4">PRINCIPLES</p>
            <h2 className="eg-display text-[1.8rem] sm:text-[2.2rem]">Built on constraints</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[#CCCCCC]">
            {[
              { num: "01", title: "Student Privacy First", desc: "Minimal data collection. No biometric storage beyond enrollment hashes. Right to deletion." },
              { num: "02", title: "No Black-Box AI", desc: "Every AI decision is explainable. Evidence is logged. Thresholds are configurable." },
              { num: "03", title: "Human Override", desc: "AI assists. Humans decide. Manual override is always available with justification." },
              { num: "04", title: "Provider Independence", desc: "Swap face recognition providers without code changes. Evidence format is standardized." },
            ].map((item) => (
              <div key={item.num} className="bg-[var(--bg-raised)] p-6 sm:p-8">
                <span className="eg-mono-sm text-[#777777] block mb-3">{item.num}</span>
                <h3 className="eg-display text-base sm:text-lg text#[FFFFFF] mb-2">{item.title}</h3>
                <p className="eg-body text-xs sm:text-sm text-[#CCCCCC]">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Roadmap */}
      <section className="bg-[var(--bg-surface)]">
        <div className="max-w-3xl mx-auto px-6 sm:px-10 py-24 sm:py-32">
          <div className="mb-12">
            <p className="eg-mono-sm text-[#777777] mb-4">DEVELOPMENT</p>
            <h2 className="eg-display text-[1.8rem] sm:text-[2.2rem]">23-phase build</h2>
          </div>
          <div className="space-y-px bg-[#CCCCCC]">
            {[
              { phase: "00–06", title: "Foundation", desc: "Models, schemas, config, admin CRUD, tests", done: true },
              { phase: "07", title: "Identity Verification", desc: "Core verification engine with provider abstraction", done: true },
              { phase: "08", title: "UniFace Integration", desc: "Face recognition provider + anti-proxy + attendance", done: false },
              { phase: "09–14", title: "Hall Tickets & Exams", desc: "Ticket generation, seat assignment, exam lifecycle", done: false },
              { phase: "15–18", title: "Monitoring & Analytics", desc: "Real-time monitoring, alerts, analytics", done: false },
              { phase: "19–23", title: "Auth & Polish", desc: "Authentication, RBAC, performance, deployment", done: false },
            ].map((item) => (
              <div key={item.phase} className="bg-[var(--bg-raised)] p-5 flex items-start gap-5">
                <span className="eg-mono-sm text-[#777777] w-10 flex-shrink-0">{item.phase}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="eg-display text-sm #[FFFFFF]">{item.title}</h3>
                    {item.done && (
                      <span className="eg-mono-sm text-[#777777] border #[777777] px-1.5 py-0.5">
                        DONE
                      </span>
                    )}
                  </div>
                  <p className="eg-body text-xs text-[#888888] mt-1">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[var(--bg-surface)] border-t border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 py-12 sm:py-16">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-8">
            <div className="col-span-2 sm:col-span-1">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 border #[777777] rotate-45" />
                <span className="eg-mono-sm text-[#777777]">EXAMGUARD</span>
              </div>
              <p className="eg-body text-[#888888] leading-relaxed">
                AI-powered examination verification for institutions that take integrity seriously.
              </p>
            </div>
            <div>
              <h4 className="eg-mono-sm text-[#777777] mb-3">SYSTEM</h4>
              <ul className="space-y-2">
              </ul>
            </div>
            <div>
              <h4 className="eg-mono-sm text-[#777777] mb-3">COMPLIANCE</h4>
              <ul className="space-y-2">
                {[
                  { label: "Privacy Policy", href: "/privacy" },
                  { label: "Terms of Service", href: "/terms" },
                ].map((item) => (
                  <li key={item.label}>
                    <a href={item.href} className="eg-body text-[#888888] #[FFFFFF] text-[#888888] hover:#[FFFFFF] transition-colors duration-200">
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="eg-mono-sm text-[#777777] mb-3">STATUS</h4>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-1 h-1 rounded-[#777777]" />
                  <span className="eg-mono-sm text-[#777777]">System operational</span>
                </div>
                <span className="eg-mono-sm #[FFFFFF] block">v0.7.0</span>
              </div>
            </div>
            <div>
              <p className="eg-mono-sm #[FFFFFF] text-center">
                EXAMGUARD — AI-POWERED EXAMINATION INTEGRITY PLATFORM
              </p>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
};