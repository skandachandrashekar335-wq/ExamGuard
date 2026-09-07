"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

const STAGES = [
  { key: "CAMERA", label: "Camera Capture", num: "01" },
  { key: "IDENTITY", label: "Identity Match", num: "02" },
  { key: "LIVENESS", label: "Liveness Detection", num: "03" },
  { key: "HALL_TICKET", label: "Hall Ticket", num: "04" },
  { key: "SEAT", label: "Seat Validation", num: "05" },
  { key: "EVIDENCE", label: "Evidence Package", num: "06" },
  { key: "DECISION", label: "Decision Engine", num: "07" },
];

export default function Home() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      {/* ── Pill Navigation ── */}
      <nav className={`eg-pill-nav${scrolled ? " eg-pill-nav--scrolled" : ""}`}>
        <Link href="/" className="eg-nav-brand">ExamGuard</Link>
        <a href="#pipeline">Pipeline</a>
        <a href="#features">Features</a>
        <a href="#security">Security</a>
        <a href="#architecture">Architecture</a>
        <Link href="/examination-sessions" className="eg-nav-cta">Access System</Link>
      </nav>

      {/* ── Mobile menu ── */}
      {mobileOpen && (
        <div className="eg-mobile-menu">
          <button className="eg-mobile-menu-close" onClick={() => setMobileOpen(false)} aria-label="Close menu">✕</button>
          <a href="#pipeline" onClick={() => setMobileOpen(false)}>Pipeline</a>
          <a href="#features" onClick={() => setMobileOpen(false)}>Features</a>
          <a href="#security" onClick={() => setMobileOpen(false)}>Security</a>
          <a href="#architecture" onClick={() => setMobileOpen(false)}>Architecture</a>
          <Link href="/examination-sessions" onClick={() => setMobileOpen(false)} className="eg-btn eg-btn-primary" style={{marginTop:"1rem",justifyContent:"center"}}>Access System</Link>
        </div>
      )}

      {/* ═══════════════════════════════════════
          HERO
         ═══════════════════════════════════════ */}
      <section className="eg-hero">
        <div className="eg-hero__atmo" aria-hidden="true">
          <div className="eg-hero__orb eg-hero__orb--sage" />
          <div className="eg-hero__orb eg-hero__orb--lavender" />
        </div>

        <div className="eg-container eg-hero__grid">
          {/* Left — Copy */}
          <div className="eg-hero__copy">
            <p className="eg-eyebrow">Examination Entry · Identity · Security</p>
            <h1 className="eg-hero__headline">
              Entry should be<br />
              <em className="eg-hero__accent">verified.</em>
            </h1>
            <p className="eg-hero__sub">
              ExamGuard connects identity verification, hall-ticket validation,
              seating, evidence collection, attendance and security into one
              auditable examination entry workflow.
            </p>
            <div className="eg-hero__actions">
              <Link href="/examination-sessions" className="eg-btn eg-btn--lg eg-btn-primary">Access System</Link>
              <a href="#pipeline" className="eg-btn eg-btn--lg">Explore Verification</a>
            </div>
          </div>

          {/* Right — Product Visualization */}
          <div className="eg-hero__visual">
            <div className="glass eg-hero__panel">
              <div className="eg-hero__panel-glow" aria-hidden="true" />
              <p className="eg-eyebrow" style={{marginBottom:"1.25rem"}}>ExamGuard Verification</p>

              {/* Camera Frame */}
              <div className="eg-hero__camera">
                <svg viewBox="0 0 200 200" className="eg-hero__face">
                  {/* Camera border */}
                  <rect x="10" y="10" width="180" height="180" rx="12" fill="none" stroke="var(--border)" strokeWidth="1.5" strokeDasharray="8 4" />
                  {/* Face outline */}
                  <ellipse cx="100" cy="85" rx="38" ry="46" fill="none" stroke="var(--accent)" strokeWidth="1.5" opacity="0.7" />
                  {/* Scan line */}
                  <line x1="40" y1="60" x2="160" y2="60" stroke="var(--accent)" strokeWidth="1" opacity="0.4">
                    <animate attributeName="y1" values="30;170;30" dur="3s" repeatCount="indefinite" />
                    <animate attributeName="y2" values="30;170;30" dur="3s" repeatCount="indefinite" />
                  </line>
                  {/* Corner brackets */}
                  <path d="M30 30 L30 50 M30 30 L50 30" stroke="var(--text-primary)" strokeWidth="2" fill="none" />
                  <path d="M170 30 L170 50 M170 30 L150 30" stroke="var(--text-primary)" strokeWidth="2" fill="none" />
                  <path d="M30 170 L30 150 M30 170 L50 170" stroke="var(--text-primary)" strokeWidth="2" fill="none" />
                  <path d="M170 170 L170 150 M170 170 L150 170" stroke="var(--text-primary)" strokeWidth="2" fill="none" />
                  {/* ID badge silhouette */}
                  <rect x="72" y="130" width="56" height="36" rx="4" fill="none" stroke="var(--border-medium)" strokeWidth="1" />
                  <circle cx="100" cy="143" r="6" fill="none" stroke="var(--border-medium)" strokeWidth="1" />
                  <line x1="85" y1="155" x2="115" y2="155" stroke="var(--border-medium)" strokeWidth="1" />
                </svg>
                <div className="eg-hero__camera-label">
                  <span className="eg-mono-sm">Camera Active</span>
                </div>
              </div>

              {/* Stage Pipeline */}
              <div className="eg-hero__stages">
                {STAGES.map((stage, i) => (
                  <div key={stage.key} className="eg-hero__stage">
                    <div className="eg-hero__stage-num">{stage.num}</div>
                    <div className="eg-hero__stage-content">
                      <span className="eg-hero__stage-key">{stage.key}</span>
                      <span className="eg-hero__stage-label">{stage.label}</span>
                    </div>
                    {i < STAGES.length - 1 && (
                      <div className="eg-hero__stage-connector" aria-hidden="true" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Social Proof Strip ── */}
      <section className="eg-proof-strip">
        <div className="eg-container">
          <div className="eg-proof-strip__grid">
            {[
              { label: "AI Perception", value: "Face + Liveness" },
              { label: "Human Review", value: "Always Available" },
              { label: "Audit Trail", value: "Every Decision" },
              { label: "Provider Agnostic", value: "Swappable AI" },
              { label: "7-Stage", value: "Verification" },
            ].map((item) => (
              <div key={item.label} className="eg-proof-strip__item">
                <p className="eg-proof-strip__label">{item.label}</p>
                <p className="eg-proof-strip__value">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          PIPELINE
         ═══════════════════════════════════════ */}
      <section id="pipeline" className="eg-section">
        <div className="eg-container">
          <div className="eg-section__header">
            <p className="eg-eyebrow">Verification Pipeline</p>
            <h2 className="eg-section__title">
              Seven stages of<br />
              <em className="eg-accent">verified entry.</em>
            </h2>
            <p className="eg-section__sub">
              Every examination entry passes through a seven-stage pipeline.
              Each stage validates evidence before progression. Human review
              remains available at every step.
            </p>
          </div>

          {/* Pipeline visual — desktop horizontal, mobile vertical */}
          <div className="eg-pipeline">
            {STAGES.map((stage, i) => (
              <div key={stage.key} className="eg-pipeline__item">
                <div className="glass eg-pipeline__card">
                  <div className="eg-pipeline__num">{stage.num}</div>
                  <div className="eg-pipeline__key">{stage.key}</div>
                  <div className="eg-pipeline__label">{stage.label}</div>
                </div>
                {i < STAGES.length - 1 && (
                  <div className="eg-pipeline__arrow" aria-hidden="true">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M5 12h14M13 6l6 6-6 6" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          AI AS PERCEPTION
         ═══════════════════════════════════════ */}
      <section className="eg-section eg-section--alt">
        <div className="eg-container">
          <div className="eg-section__header">
            <p className="eg-eyebrow">AI as Perception</p>
            <h2 className="eg-section__title">
              AI is<br />
              <em className="eg-accent">perception.</em><br />
              Not authority.
            </h2>
            <p className="eg-section__sub">
              AI produces evidence. The system evaluates evidence. Human review
              remains possible.
            </p>
          </div>

          <div className="eg-ai-flow">
            {[
              { label: "AI Provider", desc: "Perceives biometric data. Outputs evidence package.", icon: "1" },
              { label: "Evidence", desc: "Standardized format. Confidence metrics. No authorization claim.", icon: "2" },
              { label: "Decision Engine", desc: "Evaluates evidence. Applies configurable thresholds.", icon: "3" },
              { label: "Human Review", desc: "Always available. Approve, reject, or request modification.", icon: "4" },
            ].map((card, i) => (
              <div key={card.label} className="eg-ai-flow__item">
                <div className="glass eg-ai-flow__card">
                  <div className="eg-ai-flow__icon">{card.icon}</div>
                  <h3 className="eg-ai-flow__title">{card.label}</h3>
                  <p className="eg-ai-flow__desc">{card.desc}</p>
                </div>
                {i < 3 && (
                  <div className="eg-ai-flow__arrow" aria-hidden="true">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path d="M10 4v12M6 12l4 4 4-4" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          FEATURE BENTO
         ═══════════════════════════════════════ */}
      <section id="features" className="eg-section">
        <div className="eg-container">
          <div className="eg-section__header">
            <p className="eg-eyebrow">Capabilities</p>
            <h2 className="eg-section__title">
              Built into every entry.
            </h2>
          </div>

          <div className="eg-bento">
            {/* Large — Identity */}
            <div className="eg-bento__item eg-bento__item--wide">
              <div className="glass eg-bento__card eg-bento__card--tall">
                <p className="eg-eyebrow">Identity Verification</p>
                <h3 className="eg-bento__title">Face geometry meets biometric confidence.</h3>
                <p className="eg-bento__desc">1:N face matching, liveness detection, anti-spoofing. Evidence packages are provider-agnostic and auditable.</p>
                {/* Mini face visualization */}
                <div className="eg-bento__viz eg-bento__viz--face">
                  <svg viewBox="0 0 120 120" width="120" height="120">
                    <circle cx="60" cy="50" r="28" fill="none" stroke="var(--accent)" strokeWidth="1.5" opacity="0.6" />
                    <circle cx="50" cy="44" r="2.5" fill="var(--accent)" opacity="0.5" />
                    <circle cx="70" cy="44" r="2.5" fill="var(--accent)" opacity="0.5" />
                    <path d="M52 56 Q60 64 68 56" fill="none" stroke="var(--accent)" strokeWidth="1" opacity="0.5" />
                    <rect x="24" y="18" width="72" height="84" rx="6" fill="none" stroke="var(--border)" strokeWidth="1" strokeDasharray="4 3" />
                  </svg>
                </div>
                <div className="eg-bento__badges">
                  <span className="eg-badge eg-badge-success">Liveness</span>
                  <span className="eg-badge eg-badge-info">1:N Match</span>
                  <span className="eg-badge eg-badge-neutral">Anti-Spoof</span>
                </div>
              </div>
            </div>

            {/* Hall Ticket */}
            <div className="eg-bento__item">
              <div className="glass eg-bento__card">
                <p className="eg-eyebrow">Hall Ticket</p>
                <h3 className="eg-bento__title">Document validation.</h3>
                <p className="eg-bento__desc">OCR extraction, field matching, tamper detection.</p>
                <div className="eg-bento__viz eg-bento__viz--doc">
                  <div className="eg-doc-mock">
                    <div className="eg-doc-mock__photo" />
                    <div className="eg-doc-mock__lines">
                      <div className="eg-doc-mock__line eg-doc-mock__line--w80" />
                      <div className="eg-doc-mock__line eg-doc-mock__line--w60" />
                      <div className="eg-doc-mock__line eg-doc-mock__line--w70" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Seat */}
            <div className="eg-bento__item">
              <div className="glass eg-bento__card">
                <p className="eg-eyebrow">Seat Assignment</p>
                <h3 className="eg-bento__title">Right seat, right hall.</h3>
                <p className="eg-bento__desc">Seat-to-student mapping. Wrong-hall detection.</p>
                <div className="eg-bento__viz eg-bento__viz--seat">
                  <div className="eg-seat-grid">
                    {Array.from({length:12}).map((_,i)=>(
                      <div key={i} className={`eg-seat-grid__cell${i===7?" eg-seat-grid__cell--active":""}${i===3?" eg-seat-grid__cell--warn":""}`} />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Attendance */}
            <div className="eg-bento__item">
              <div className="glass eg-bento__card">
                <p className="eg-eyebrow">Attendance</p>
                <h3 className="eg-bento__title">Entry timestamped.</h3>
                <p className="eg-bento__desc">Real-time attendance tracking. Entry-point logging.</p>
                <div className="eg-bento__viz eg-bento__viz--timeline">
                  {[0,1,2,3].map(i=>(
                    <div key={i} className="eg-timeline__row">
                      <div className="eg-timeline__dot" />
                      <div className="eg-timeline__bar" style={{width:`${60+i*10}%`}} />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Security */}
            <div className="eg-bento__item">
              <div className="glass eg-bento__card">
                <p className="eg-eyebrow">Monitoring</p>
                <h3 className="eg-bento__title">Live session view.</h3>
                <p className="eg-bento__desc">Active sessions, gate status, capacity tracking.</p>
                <div className="eg-bento__viz eg-bento__viz--monitor">
                  <div className="eg-monitor-bars">
                    {[40,65,80,55,90,45,70].map((h,i)=>(
                      <div key={i} className="eg-monitor-bars__bar" style={{height:`${h}%`}} />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          SECURITY SIGNALS
         ═══════════════════════════════════════ */}
      <section id="security" className="eg-section eg-section--alt">
        <div className="eg-container">
          <div className="eg-section__header">
            <p className="eg-eyebrow">Security Signals</p>
            <h2 className="eg-section__title">
              Every decision<br />is guarded.
            </h2>
          </div>

          <div className="eg-signals-bento">
            <div className="eg-signals-bento__row eg-signals-bento__row--top">
              <div className="glass eg-signal-card eg-signal-card--danger eg-signal-card--wide">
                <div className="eg-signal-card__indicator" style={{background:"var(--danger)"}} />
                <div>
                  <p className="eg-signal-card__title">Identity Mismatch</p>
                  <p className="eg-signal-card__desc">Biometric mismatch between live capture and enrolled identity.</p>
                </div>
              </div>
              <div className="glass eg-signal-card eg-signal-card--danger">
                <div className="eg-signal-card__indicator" style={{background:"var(--danger)"}} />
                <div>
                  <p className="eg-signal-card__title">Liveness Spoof</p>
                  <p className="eg-signal-card__desc">Anti-spoofing layer detected presentation attack.</p>
                </div>
              </div>
            </div>
            <div className="eg-signals-bento__row">
              <div className="glass eg-signal-card eg-signal-card--warning">
                <div className="eg-signal-card__indicator" style={{background:"var(--warning)"}} />
                <div>
                  <p className="eg-signal-card__title">Wrong Hall</p>
                  <p className="eg-signal-card__desc">Candidate attempting entry in unassigned examination hall.</p>
                </div>
              </div>
              <div className="glass eg-signal-card eg-signal-card--warning">
                <div className="eg-signal-card__indicator" style={{background:"var(--warning)"}} />
                <div>
                  <p className="eg-signal-card__title">Wrong Entry Point</p>
                  <p className="eg-signal-card__desc">Candidate entered through a different gate than assigned.</p>
                </div>
              </div>
              <div className="glass eg-signal-card eg-signal-card--info">
                <div className="eg-signal-card__indicator" style={{background:"var(--info)"}} />
                <div>
                  <p className="eg-signal-card__title">Repeated Failed Verification</p>
                  <p className="eg-signal-card__desc">Multiple consecutive verification failures for a session.</p>
                </div>
              </div>
            </div>
            <div className="eg-signals-bento__row">
              <div className="glass eg-signal-card eg-signal-card--info eg-signal-card--wide">
                <div className="eg-signal-card__indicator" style={{background:"var(--info)"}} />
                <div>
                  <p className="eg-signal-card__title">Document Anomaly</p>
                  <p className="eg-signal-card__desc">OCR confidence below threshold or field mismatch detected.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          ARCHITECTURE
         ═══════════════════════════════════════ */}
      <section id="architecture" className="eg-section">
        <div className="eg-container">
          <div className="eg-arch">
            <div className="eg-arch__copy">
              <p className="eg-eyebrow">Architecture</p>
              <h2 className="eg-section__title">
                Evidence in.<br />
                <em className="eg-accent">Decisions out.</em>
              </h2>
              <p className="eg-section__sub">
                ExamGuard separates what the AI sees from what the system decides.
                Provider output is evidence — never a direct authorization decision.
              </p>
              <ul className="eg-arch__list">
                <li>Provider-agnostic integration</li>
                <li>Evidence ≠ decision</li>
                <li>Configurable thresholds</li>
                <li>Full audit trail</li>
              </ul>
            </div>
            <div className="eg-arch__flow">
              <div className="glass eg-arch__card">
                <span className="eg-arch__card-num">01</span>
                <div>
                  <p className="eg-arch__card-title">AI / Provider</p>
                  <p className="eg-arch__card-desc">Captures biometric data, outputs evidence</p>
                </div>
              </div>
              <div className="eg-arch__connector" aria-hidden="true" />
              <div className="glass eg-arch__card">
                <span className="eg-arch__card-num">02</span>
                <div>
                  <p className="eg-arch__card-title">Evidence Package</p>
                  <p className="eg-arch__card-desc">Standardized, auditable, provider-agnostic</p>
                </div>
              </div>
              <div className="eg-arch__connector" aria-hidden="true" />
              <div className="glass eg-arch__card">
                <span className="eg-arch__card-num">03</span>
                <div>
                  <p className="eg-arch__card-title">Decision Engine</p>
                  <p className="eg-arch__card-desc">Evaluates against configurable thresholds</p>
                </div>
              </div>
              <div className="eg-arch__connector" aria-hidden="true" />
              <div className="glass eg-arch__card">
                <span className="eg-arch__card-num">04</span>
                <div>
                  <p className="eg-arch__card-title">Human Review</p>
                  <p className="eg-arch__card-desc">Always available with full audit trail</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          PRINCIPLES
         ═══════════════════════════════════════ */}
      <section className="eg-section eg-section--alt">
        <div className="eg-container">
          <div className="eg-section__header">
            <p className="eg-eyebrow">Principles</p>
            <h2 className="eg-section__title">Built on constraints.</h2>
          </div>
          <div className="eg-principles">
            {[
              { num: "01", title: "Student Privacy First", desc: "Minimal data collection. No biometric storage beyond enrollment hashes. Right to deletion." },
              { num: "02", title: "No Black-Box AI", desc: "Every AI decision is explainable. Evidence is logged. Thresholds are configurable." },
              { num: "03", title: "Human Override", desc: "AI assists. Humans decide. Manual override is always available with justification." },
              { num: "04", title: "Provider Independence", desc: "Swap face recognition providers without code changes. Evidence format is standardized." },
            ].map((item) => (
              <div key={item.num} className="glass eg-principle">
                <span className="eg-principle__num">{item.num}</span>
                <h3 className="eg-principle__title">{item.title}</h3>
                <p className="eg-principle__desc">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════
          CTA
         ═══════════════════════════════════════ */}
      <section className="eg-section">
        <div className="eg-container" style={{textAlign:"center",maxWidth:"640px"}}>
          <h2 className="eg-section__title" style={{marginBottom:"1.5rem"}}>
            Examination integrity,<br />
            <em className="eg-accent">built into every entry.</em>
          </h2>
          <p className="eg-section__sub" style={{marginBottom:"2.5rem"}}>
            Connect your institution&apos;s examination workflow with
            AI-powered verification that leaves a complete audit trail.
          </p>
          <div style={{display:"flex",gap:"0.75rem",justifyContent:"center",flexWrap:"wrap"}}>
            <Link href="/examination-sessions" className="eg-btn eg-btn--lg eg-btn-primary">Access System</Link>
            <Link href="/privacy" className="eg-btn eg-btn--lg">Privacy Policy</Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="eg-footer">
        <div className="eg-container">
          <div className="eg-footer__grid">
            <div className="eg-footer__brand">
              <p className="eg-footer__logo">ExamGuard</p>
              <p className="eg-footer__tagline">AI-powered examination verification for institutions that take integrity seriously.</p>
            </div>
            <div className="eg-footer__col">
              <p className="eg-footer__heading">System</p>
              <Link href="/dashboard">Dashboard</Link>
              <Link href="/examination-sessions">Sessions</Link>
              <Link href="/monitoring">Monitoring</Link>
            </div>
            <div className="eg-footer__col">
              <p className="eg-footer__heading">Compliance</p>
              <Link href="/privacy">Privacy Policy</Link>
              <Link href="/terms">Terms of Service</Link>
            </div>
            <div className="eg-footer__col">
              <p className="eg-footer__heading">Status</p>
              <div className="eg-footer__status">
                <span className="eg-footer__dot" />
                <span>System operational</span>
              </div>
              <span className="eg-footer__version">v0.7.0</span>
            </div>
          </div>
          <div className="eg-footer__bottom">
            <p>ExamGuard — AI-Powered Examination Integrity Platform</p>
          </div>
        </div>
      </footer>
    </>
  );
}
