"use client";

import React from "react";

interface HallTicketVizProps {
  progress: number;
  subProgress: number;
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * Math.max(0, Math.min(1, t));
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v));
}

function HallTicketVizInner({ progress, subProgress }: HallTicketVizProps) {
  const scanY = lerp(20, 200, subProgress * 0.8);
  const scanOpacity = subProgress < 0.05 ? 0 : subProgress > 0.9 ? 0 : 0.3;

  const fieldReveal = (index: number) => {
    const threshold = index * 0.2;
    return clamp((subProgress - threshold) * 3, 0, 1);
  };

  return (
    <div className="relative w-full max-w-[280px] mx-auto">
      <svg viewBox="0 0 260 200" className="w-full" fill="none">
        {/* Document outline */}
        <rect x="20" y="10" width="220" height="180" stroke="var(--white)" strokeWidth="0.5" opacity={0.2} />

        {/* Corner marks */}
        <polyline points="20,30 20,10 40,10" stroke="var(--white)" strokeWidth="0.8" opacity={0.3} />
        <polyline points="220,10 240,10 240,30" stroke="var(--white)" strokeWidth="0.8" opacity={0.3} />
        <polyline points="240,170 240,190 220,190" stroke="var(--white)" strokeWidth="0.8" opacity={0.3} />
        <polyline points="40,190 20,190 20,170" stroke="var(--white)" strokeWidth="0.8" opacity={0.3} />

        {/* Header line */}
        <line x1="20" y1="40" x2="240" y2="40" stroke="var(--white)" strokeWidth="0.3" opacity={0.15} />

        {/* Scan line */}
        <line x1="20" y1={scanY} x2="240" y2={scanY} stroke="var(--white)" strokeWidth="0.5" opacity={scanOpacity} />

        {/* Fields — truthful empty states */}
        {[
          { label: "STUDENT", value: "NOT CONNECTED", y: 55 },
          { label: "REGISTRATION", value: "AWAITING DATA", y: 80 },
          { label: "EXAM", value: "AWAITING DATA", y: 105 },
          { label: "HALL TICKET", value: "NOT LOADED", y: 130 },
        ].map((field, i) => (
          <g key={field.label} opacity={fieldReveal(i)}>
            <text x="30" y={field.y} fill="var(--white)" fontSize="5" fontFamily="var(--font-mono)" letterSpacing="0.1em" opacity={0.4}>
              {field.label}
            </text>
            <text x="30" y={field.y + 10} fill="var(--white)" fontSize="7" fontFamily="var(--font-mono)" letterSpacing="0.05em" opacity={0.7}>
              {field.value}
            </text>
          </g>
        ))}

        {/* Pipeline diagram */}
        <g opacity={clamp((subProgress - 0.6) * 4, 0, 0.4)}>
          <line x1="30" y1="155" x2="230" y2="155" stroke="var(--white)" strokeWidth="0.3" strokeDasharray="2 3" />
          {["TICKET", "STUDENT", "EXAM", "VERIFY"].map((step, i) => (
            <g key={step}>
              <circle cx={60 + i * 55} cy={155} r={3} stroke="var(--white)" strokeWidth="0.4" fill="none" />
              <text x={60 + i * 55} y={168} fill="var(--white)" fontSize="4" fontFamily="var(--font-mono)" textAnchor="middle" letterSpacing="0.05em" opacity={0.5}>
                {step}
              </text>
            </g>
          ))}
          {/* Arrows */}
          {[0, 1, 2].map((i) => (
            <line key={`a-${i}`} x1={73 + i * 55} y1={155} x2={92 + i * 55} y2={155} stroke="var(--white)" strokeWidth="0.3" markerEnd="url(#arrow)" />
          ))}
        </g>

        <defs>
          <marker id="arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--white)" opacity={0.4} />
          </marker>
        </defs>
      </svg>
    </div>
  );
}

const HallTicketViz = React.memo(HallTicketVizInner);
export default HallTicketViz;
