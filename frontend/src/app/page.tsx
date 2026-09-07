"use client";

import { useRef, useEffect, useState } from "react";

const STAGES = [
  { key: "CAMERA", label: "Camera Capture" },
  { key: "IDENTITY", label: "Identity Match" },
  { key: "LIVENESS", label: "Liveness Detection" },
  { key: "HALL_TICKET", label: "Hall Ticket" },
  { key: "SEAT", label: "Seat Validation" },
  { key: "EVIDENCE", label: "Evidence Package" },
  { key: "DECISION", label: "Decision Engine" },
];

export default function Home() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const pipelineRef = useRef<HTMLDivElement>(null);
  const [pipelineProgress, setPipelineProgress] = useState(0);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!pipelineRef.current) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          let c = 0;
          const iv = setInterval(() => {
            c += 2;
            setPipelineProgress(c);
            if (c >= 100) clearInterval(iv);
          }, 25);
          obs.disconnect();
        }
      },
      { threshold: 0.3 }
    );
    obs.observe(pipelineRef.current);
    return () => obs.disconnect();
  }, []);

  return (
    <>
      {/* Pill Navigation */}
      <nav className={`eg-pill-nav ${scrolled ? "shadow-lg" : ""}`}>
        <a href="/" className="eg-nav-brand">ExamGuard</a>
        <a href="#pipeline">Pipeline</a>
        <a href="#features">Features</a>
        <a href="#security">Security</a>
        <a href="#architecture">Architecture</a>
        <a href="/examination-sessions" className="eg-nav-cta">Access System</a>
      </nav>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="eg-mobile-menu">
          <button className="eg-mobile-menu-close" onClick={() => setMobileOpen(false)}>✕</button>
          <a href="#pipeline" onClick={() => setMobileOpen(false)}>Pipeline</a>
          <a href="#features" onClick={() => setMobileOpen(false)}>Features</a>
          <a href="#security" onClick={() => setMobileOpen(false)}>Security</a>
          <a href="#architecture" onClick={() => setMobileOpen(false)}>Architecture</a>
          <a href="/examination-sessions" className="eg-btn eg-btn-primary mt-4 text-center">Access System</a>
        </div>
      )}

      {/* Hero */}
      <section className="relative min-h-screen flex items-center overflow-hidden pt-28 pb-20">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-1/4 w-[500px] h-[500px] rounded-full bg-[var(--atmo-sage)] opacity-40 blur-[100px]" />
          <div className="absolute bottom-20 right-1/4 w-[400px] h-[400px] rounded-full bg-[var(--atmo-lavender)] opacity-30 blur-[80px]" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 sm:px-10 w-full">
          <div className="grid lg:grid-cols-12 gap-12 items-center">
            {/* Left */}
            <div className="lg:col-span-6">
              <p className="eg-mono-sm text-[var(--text-muted)] mb-5 tracking-widest">
                EXAM ENTRY · IDENTITY · SECURITY
              </p>
              <h1 className="text-[clamp(2.5rem,5.5vw,4.5rem)] leading-[1.02] tracking-[-0.03em] mb-6" style={{ fontFamily: "var(--font-display)" }}>
                Entry should be
                <br />
                <span className="italic" style={{ color: "var(--accent)" }}>verified.</span>
              </h1>
              <p className="text-lg text-[var(--text-muted)] max-w-md mb-10 leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>
                AI-powered examination entry verification connecting identity,
                hall-ticket, seating, evidence and attendance into one auditable
                workflow.
              </p>
              <div className="flex flex-wrap gap-3">
                <a href="/examination-sessions" className="eg-btn eg-btn-primary px-6 py-3 text-sm">
                  Access System
                </a>
                <a href="#pipeline" className="eg-btn px-6 py-3 text-sm">
                  Explore Verification
                </a>
              </div>
            </div>

            {/* Right — Verification Panel */}
            <div className="lg:col-span-6">
              <div className="glass rounded-[var(--radius-xl)] p-6 sm:p-8 relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--border-glass-strong)] to-transparent" />
                <p className="eg-mono-sm text-[var(--text-muted)] mb-5 tracking-widest">EXAMINATION ENTRY VERIFICATION</p>

                {/* Verification Ring */}
                <div className="flex justify-center mb-6">
                  <svg width="140" height="140" viewBox="0 0 140 140">
                    <circle cx="70" cy="70" r="60" fill="none" stroke="var(--border)" strokeWidth="2" />
                    <circle
                      cx="70" cy="70" r="60"
                      fill="none" stroke="var(--accent)" strokeWidth="2.5"
                      strokeDasharray="377"
                      strokeDashoffset={377 - (377 * 0.72)}
                      strokeLinecap="round"
                      transform="rotate(-90 70 70)"
                      style={{ animation: "eg-ring-draw 1.5s ease-out both" }}
                    />
                    <circle cx="70" cy="70" r="48" fill="none" stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
                    <circle
                      cx="70" cy="70" r="48"
                      fill="none" stroke="var(--success)" strokeWidth="2"
                      strokeDasharray="301"
                      strokeDashoffset={301 - (301 * 0.88)}
                      strokeLinecap="round"
                      transform="rotate(-90 70 70)"
                      style={{ animation: "eg-ring-draw 1.8s ease-out 0.3s both" }}
                    />
                    <text x="70" y="66" textAnchor="middle" fontFamily="var(--font-display)" fontSize="22" fontWeight="500" fill="var(--text-primary)">72%</text>
                    <text x="70" y="82" textAnchor="middle" fontFamily="var(--font-mono)" fontSize="8" letterSpacing="0.1em" fill="var(--text-muted)">CONFIDENCE</text>
                  </svg>
                </div>

                {/* Stage Indicators */}
                <div className="space-y-2.5">
                  {STAGES.map((stage, i) => (
                    <div key={stage.key} className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium shrink-0"
                        style={{
                          background: i < 5 ? "var(--success-bg)" : i === 5 ? "var(--info-bg)" : "rgba(26,46,31,0.05)",
                          color: i < 5 ? "var(--success)" : i === 5 ? "var(--info)" : "var(--text-muted)",
                          border: `1px solid ${i < 5 ? "rgba(45,159,111,0.2)" : i === 5 ? "rgba(74,144,200,0.2)" : "var(--border)"}`,
                        }}>
                        {i < 5 ? "✓" : i === 5 ? "→" : (i + 1)}
                      </div>
                      <span className="text-sm" style={{
                        fontFamily: "var(--font-body)",
                        color: i < 5 ? "var(--text-primary)" : "var(--text-muted)",
                      }}>{stage.label}</span>
                      {i < 5 && <span className="eg-mono-sm text-[var(--success)] ml-auto">✓</span>}
                      {i === 5 && <span className="eg-mono-sm text-[var(--info)] ml-auto">IN PROGRESS</span>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Social Proof Strip */}
      <section className="py-8 border-y border-[var(--border)]" style={{ background: "rgba(255,255,255,0.3)" }}>
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-6 text-center">
            {[
              { label: "AI PERCEPTION", value: "Face + Liveness" },
              { label: "HUMAN REVIEW", value: "Always Available" },
              { label: "AUDIT TRAIL", value: "Every Decision" },
              { label: "PROVIDER AGNOSTIC", value: "Swappable AI" },
              { label: "7-STAGE", value: "Verification" },
            ].map((item) => (
              <div key={item.label}>
                <p className="eg-mono-sm text-[var(--text-muted)] mb-1">{item.label}</p>
                <p className="text-sm font-medium text-[var(--text-primary)]" style={{ fontFamily: "var(--font-body)" }}>{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 7-Stage Pipeline */}
      <section id="pipeline" ref={pipelineRef} className="py-24 sm:py-32">
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="grid lg:grid-cols-2 gap-16 items-start">
            <div>
              <p className="eg-mono-sm text-[var(--text-muted)] mb-4 tracking-widest">VERIFICATION PIPELINE</p>
              <h2 className="text-[clamp(2rem,4vw,3rem)] leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: "var(--font-display)" }}>
                Seven stages of
                <br />
                <span className="italic" style={{ color: "var(--accent)" }}>verified entry.</span>
              </h2>
              <p className="text-[var(--text-muted)] leading-relaxed mb-8 max-w-md">
                Every examination entry passes through a seven-stage pipeline.
                Each stage validates evidence before progression. Human review
                remains available at every step.
              </p>
              <div className="eg-progress-line" style={{ "--progress": `${pipelineProgress}%` } as React.CSSProperties} />
            </div>

            <div className="space-y-3">
              {STAGES.map((stage, i) => (
                <div key={stage.key} className="glass-surface rounded-[var(--radius-md)] px-5 py-4 flex items-center gap-4 transition-all hover:shadow-md"
                  style={{ animationDelay: `${i * 80}ms` }}>
                  <span className="eg-mono-sm text-[var(--text-muted)] w-8 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                  <span className="eg-mono-sm text-[var(--accent)] shrink-0 w-28">{stage.key}</span>
                  <span className="text-sm text-[var(--text-secondary)]" style={{ fontFamily: "var(--font-body)" }}>{stage.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* AI as Perception */}
      <section className="py-24 sm:py-32" style={{ background: "rgba(255,255,255,0.25)" }}>
        <div className="max-w-5xl mx-auto px-6 sm:px-10">
          <div className="text-center mb-16">
            <p className="eg-mono-sm text-[var(--text-muted)] mb-4 tracking-widest">AI AS PERCEPTION</p>
            <h2 className="text-[clamp(2rem,4vw,3.25rem)] leading-[1.08] tracking-[-0.02em] mb-5" style={{ fontFamily: "var(--font-display)" }}>
              AI is <span className="italic">perception.</span>
              <br />Not authority.
            </h2>
            <p className="text-[var(--text-muted)] max-w-lg mx-auto leading-relaxed">
              AI produces evidence. The system evaluates evidence. Human review
              remains possible. The decision engine evaluates evidence against
              configurable thresholds.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "AI", desc: "Perceives biometric data. Outputs evidence package.", icon: "◎" },
              { label: "EVIDENCE", desc: "Standardized format. Confidence metrics. No authorization claim.", icon: "◻" },
              { label: "DECISION ENGINE", desc: "Evaluates evidence. Applies thresholds. Supports override.", icon: "◈" },
              { label: "HUMAN REVIEW", desc: "Always available. Approve, reject, or request modification.", icon: "◉" },
            ].map((card) => (
              <div key={card.label} className="glass rounded-[var(--radius-lg)] p-6">
                <div className="w-10 h-10 rounded-[var(--radius-md)] flex items-center justify-center text-lg mb-4"
                  style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                  {card.icon}
                </div>
                <p className="eg-mono-sm text-[var(--text-muted)] mb-2 tracking-widest">{card.label}</p>
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>{card.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature Bento Grid */}
      <section id="features" className="py-24 sm:py-32">
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="text-center mb-16">
            <p className="eg-mono-sm text-[var(--text-muted)] mb-4 tracking-widest">CAPABILITIES</p>
            <h2 className="text-[clamp(2rem,4vw,3rem)] leading-[1.1] tracking-[-0.02em]" style={{ fontFamily: "var(--font-display)" }}>
              Built into every entry.
            </h2>
          </div>

          <div className="grid md:grid-cols-12 gap-4">
            {/* Large card */}
            <div className="md:col-span-7 glass rounded-[var(--radius-xl)] p-8 relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--border-glass-strong)] to-transparent" />
              <p className="eg-mono-sm text-[var(--text-muted)] mb-3 tracking-widest">IDENTITY VERIFICATION</p>
              <h3 className="text-xl mb-3" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>Face geometry meets biometric confidence.</h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed mb-6 max-w-md">1:N face matching, liveness detection, anti-spoofing. Evidence packages are provider-agnostic and auditable.</p>
              <div className="flex gap-2">
                <span className="eg-badge eg-badge-success">LIVENESS</span>
                <span className="eg-badge eg-badge-info">1:N MATCH</span>
                <span className="eg-badge eg-badge-neutral">ANTI-SPOOF</span>
              </div>
            </div>

            {/* Small card */}
            <div className="md:col-span-5 glass rounded-[var(--radius-xl)] p-8">
              <p className="eg-mono-sm text-[var(--text-muted)] mb-3 tracking-widest">HALL TICKET</p>
              <h3 className="text-xl mb-3" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>Document validation.</h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed mb-4">OCR extraction, field matching, tamper detection.</p>
              <div className="space-y-2">
                {["Exam Name", "Roll Number", "Photo", "Hall / Seat"].map((f) => (
                  <div key={f} className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)]" />
                    {f}
                  </div>
                ))}
              </div>
            </div>

            {/* Medium cards row */}
            <div className="md:col-span-4 glass rounded-[var(--radius-xl)] p-6">
              <p className="eg-mono-sm text-[var(--text-muted)] mb-2 tracking-widest">SEAT ASSIGNMENT</p>
              <h3 className="text-lg mb-2" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>Right seat, right hall.</h3>
              <p className="text-sm text-[var(--text-muted)]">Seat-to-student mapping. Wrong-hall detection.</p>
            </div>
            <div className="md:col-span-4 glass rounded-[var(--radius-xl)] p-6">
              <p className="eg-mono-sm text-[var(--text-muted)] mb-2 tracking-widest">ATTENDANCE</p>
              <h3 className="text-lg mb-2" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>Entry timestamped.</h3>
              <p className="text-sm text-[var(--text-muted)]">Real-time attendance. Entry-point tracking.</p>
            </div>
            <div className="md:col-span-4 glass rounded-[var(--radius-xl)] p-6">
              <p className="eg-mono-sm text-[var(--text-muted)] mb-2 tracking-widest">MONITORING</p>
              <h3 className="text-lg mb-2" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>Live session view.</h3>
              <p className="text-sm text-[var(--text-muted)]">Active sessions, gate status, capacity.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Security Signals */}
      <section id="security" className="py-24 sm:py-32" style={{ background: "rgba(255,255,255,0.25)" }}>
        <div className="max-w-6xl mx-auto px-6 sm:px-10">
          <div className="text-center mb-16">
            <p className="eg-mono-sm text-[var(--text-muted)] mb-4 tracking-widest">SECURITY SIGNALS</p>
            <h2 className="text-[clamp(1.75rem,3.5vw,2.75rem)] leading-[1.1] tracking-[-0.02em]" style={{ fontFamily: "var(--font-display)" }}>
              Every decision is guarded.
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { signal: "IDENTITY MISMATCH", desc: "Biometric mismatch between live capture and enrolled identity.", severity: "danger" },
              { signal: "LIVENESS SPOOF", desc: "Anti-spoofing layer detected presentation attack.", severity: "danger" },
              { signal: "WRONG HALL", desc: "Candidate attempting entry in unassigned examination hall.", severity: "warning" },
              { signal: "WRONG ENTRY POINT", desc: "Candidate entered through a different gate than assigned.", severity: "warning" },
              { signal: "REPEATED FAILED VERIFICATION", desc: "Multiple consecutive verification failures for a session.", severity: "info" },
              { signal: "DOCUMENT ANOMALY", desc: "OCR confidence below threshold or field mismatch detected.", severity: "info" },
            ].map((item) => (
              <div key={item.signal} className="glass-surface rounded-[var(--radius-md)] p-5" style={{ borderLeftColor: `var(--${item.severity})`, borderLeftWidth: "3px" }}>
                <p className="eg-mono-sm text-[var(--text-primary)] mb-2 tracking-wider">{item.signal}</p>
                <p className="text-sm text-[var(--text-muted)] leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="py-24 sm:py-32">
        <div className="max-w-5xl mx-auto px-6 sm:px-10">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <p className="eg-mono-sm text-[var(--text-muted)] mb-4 tracking-widest">ARCHITECTURE</p>
              <h2 className="text-[clamp(1.75rem,3.5vw,2.75rem)] leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: "var(--font-display)" }}>
                Evidence in.
                <br />
                <span className="italic">Decisions out.</span>
              </h2>
              <p className="text-[var(--text-muted)] leading-relaxed mb-8">
                ExamGuard separates what the AI sees from what the system decides.
                Provider output is evidence — never a direct authorization decision.
              </p>
              <div className="space-y-3">
                {["Provider-agnostic integration", "Evidence ≠ decision", "Configurable thresholds", "Full audit trail"].map((item) => (
                  <div key={item} className="flex items-center gap-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                    <span className="text-sm text-[var(--text-secondary)]" style={{ fontFamily: "var(--font-body)" }}>{item}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              {[
                { stage: "ENTRY", desc: "Hall ticket + student context" },
                { stage: "LIVENESS", desc: "Anti-spoofing detection" },
                { stage: "DECISION", desc: "Evidence threshold evaluation" },
                { stage: "AUDIT", desc: "Full decision trail" },
              ].map((item) => (
                <div key={item.stage} className="glass-surface rounded-[var(--radius-md)] px-5 py-4 flex items-start gap-4">
                  <span className="eg-mono-sm text-[var(--accent)] w-16 shrink-0 pt-0.5">{item.stage}</span>
                  <span className="text-sm text-[var(--text-secondary)]" style={{ fontFamily: "var(--font-body)" }}>{item.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Principles */}
      <section className="py-24 sm:py-32" style={{ background: "rgba(255,255,255,0.25)" }}>
        <div className="max-w-5xl mx-auto px-6 sm:px-10">
          <div className="mb-12">
            <p className="eg-mono-sm text-[var(--text-muted)] mb-4 tracking-widest">PRINCIPLES</p>
            <h2 className="text-[clamp(1.75rem,3.5vw,2.5rem)] leading-[1.1] tracking-[-0.02em]" style={{ fontFamily: "var(--font-display)" }}>
              Built on constraints.
            </h2>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              { num: "01", title: "Student Privacy First", desc: "Minimal data collection. No biometric storage beyond enrollment hashes. Right to deletion." },
              { num: "02", title: "No Black-Box AI", desc: "Every AI decision is explainable. Evidence is logged. Thresholds are configurable." },
              { num: "03", title: "Human Override", desc: "AI assists. Humans decide. Manual override is always available with justification." },
              { num: "04", title: "Provider Independence", desc: "Swap face recognition providers without code changes. Evidence format is standardized." },
            ].map((item) => (
              <div key={item.num} className="glass rounded-[var(--radius-lg)] p-6">
                <span className="eg-mono-sm text-[var(--text-muted)] block mb-3">{item.num}</span>
                <h3 className="text-lg mb-2" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>{item.title}</h3>
                <p className="text-sm text-[var(--text-muted)] leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 sm:py-32">
        <div className="max-w-3xl mx-auto px-6 sm:px-10 text-center">
          <h2 className="text-[clamp(2rem,4vw,3rem)] leading-[1.1] tracking-[-0.02em] mb-6" style={{ fontFamily: "var(--font-display)" }}>
            Examination integrity,<br />
            <span className="italic" style={{ color: "var(--accent)" }}>built into every entry.</span>
          </h2>
          <p className="text-[var(--text-muted)] mb-10 max-w-md mx-auto">
            Connect your institution&apos;s examination workflow with
            AI-powered verification that leaves a complete audit trail.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <a href="/examination-sessions" className="eg-btn eg-btn-primary px-8 py-3">Access System</a>
            <a href="/privacy" className="eg-btn px-8 py-3">Privacy Policy</a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-[var(--border)]" style={{ background: "rgba(255,255,255,0.2)" }}>
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div className="col-span-2 md:col-span-1">
              <p className="text-sm font-medium mb-2" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>ExamGuard</p>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                AI-powered examination verification for institutions that take integrity seriously.
              </p>
            </div>
            <div>
              <p className="eg-mono-sm text-[var(--text-muted)] mb-3">SYSTEM</p>
              <div className="space-y-1.5">
                <a href="/dashboard" className="block text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Dashboard</a>
                <a href="/examination-sessions" className="block text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Sessions</a>
                <a href="/monitoring" className="block text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Monitoring</a>
              </div>
            </div>
            <div>
              <p className="eg-mono-sm text-[var(--text-muted)] mb-3">COMPLIANCE</p>
              <div className="space-y-1.5">
                <a href="/privacy" className="block text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Privacy Policy</a>
                <a href="/terms" className="block text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Terms of Service</a>
              </div>
            </div>
            <div>
              <p className="eg-mono-sm text-[var(--text-muted)] mb-3">STATUS</p>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-2 h-2 rounded-full bg-[var(--success)]" />
                <span className="eg-mono-sm text-[var(--text-muted)]">System operational</span>
              </div>
              <span className="eg-mono-sm text-[var(--text-faint)]">v0.7.0</span>
            </div>
          </div>
          <div className="mt-10 pt-6 border-t border-[var(--border)] text-center">
            <p className="eg-mono-sm text-[var(--text-faint)]">
              EXAMGUARD — AI-POWERED EXAMINATION INTEGRITY PLATFORM
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
