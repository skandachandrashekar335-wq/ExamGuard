"use client";

import { useRef, useEffect, useState } from "react";

interface FaceGeometryProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  progress: number;
  mouseX: number;
  mouseY: number;
}

const LANDMARKS = [
  { x: 200, y: 80, label: "forehead" },
  { x: 140, y: 120, label: "left_brow" },
  { x: 260, y: 120, label: "right_brow" },
  { x: 120, y: 160, label: "left_eye_outer" },
  { x: 160, y: 155, label: "left_eye" },
  { x: 200, y: 150, label: "nose_bridge" },
  { x: 240, y: 155, label: "right_eye" },
  { x: 280, y: 160, label: "right_eye_outer" },
  { x: 200, y: 200, label: "nose_tip" },
  { x: 160, y: 230, label: "left_mouth" },
  { x: 200, y: 240, label: "mouth_center" },
  { x: 240, y: 230, label: "right_mouth" },
  { x: 200, y: 280, label: "chin" },
  { x: 130, y: 250, label: "left_jaw" },
  { x: 270, y: 250, label: "right_jaw" },
];

const CONNECTIONS = [
  [0, 1], [0, 2], [1, 3], [1, 4], [2, 6], [2, 7],
  [3, 4], [6, 7], [4, 5], [5, 6], [5, 9], [9, 10],
  [10, 11], [11, 12], [8, 5], [8, 10], [13, 3], [13, 9],
  [14, 7], [14, 11], [0, 5], [5, 8], [8, 12], [12, 13], [12, 14],
];

export default function FaceGeometry({ stage, progress, mouseX, mouseY }: FaceGeometryProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [time, setTime] = useState(0);

  useEffect(() => {
    let raf: number;
    const tick = () => {
      setTime((t) => t + 0.016);
      raf = requestAnimationFrame(tick);
    };
    if (stage !== "ready") {
      raf = requestAnimationFrame(tick);
    }
    return () => cancelAnimationFrame(raf);
  }, [stage]);

  const isActive = stage !== "ready";
  const scanY = (time * 40) % 360;
  const parallaxX = mouseX * 8;
  const parallaxY = mouseY * 5;

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 400 360"
      className="w-full h-full max-w-[500px] mx-auto"
      style={{ filter: isActive ? "none" : "grayscale(0.5) opacity(0.4)" }}
    >
      <defs>
        <radialGradient id="face-glow" cx="50%" cy="45%" r="45%">
          <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0.08" />
          <stop offset="100%" stopColor="transparent" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="scan-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0" />
          <stop offset="50%" stopColor="var(--accent-cyan)" stopOpacity="0.6" />
          <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Grid */}
      <g opacity={isActive ? 0.15 : 0.05} transform={`translate(${parallaxX * 0.2}, ${parallaxY * 0.2})`}>
        {Array.from({ length: 19 }, (_, i) => (
          <line key={`v${i}`} x1={i * 20} y1={0} x2={i * 20} y2={360} stroke="var(--accent-cyan)" strokeWidth="0.5" />
        ))}
        {Array.from({ length: 19 }, (_, i) => (
          <line key={`h${i}`} x1={0} y1={i * 20} x2={400} y2={360} stroke="var(--accent-cyan)" strokeWidth="0.5" />
        ))}
      </g>

      {/* Face glow */}
      <circle cx="200" cy="180" r="140" fill="url(#face-glow)" />

      {/* Outer frame */}
      <rect
        x="100" y="40" width="200" height="280" rx="16"
        fill="none"
        stroke={isActive ? "var(--accent-cyan)" : "#333"}
        strokeWidth={isActive ? "1.5" : "0.5"}
        strokeDasharray={isActive ? "none" : "4 4"}
        opacity={isActive ? 0.6 : 0.3}
        transform={`translate(${parallaxX * 0.3}, ${parallaxY * 0.3})`}
      />

      {/* Crosshair */}
      {isActive && (
        <g opacity="0.2" transform={`translate(${parallaxX * 0.15}, ${parallaxY * 0.15})`}>
          <line x1="200" y1="60" x2="200" y2="100" stroke="var(--accent-cyan)" strokeWidth="0.5" />
          <line x1="200" y1="260" x2="200" y2="300" stroke="var(--accent-cyan)" strokeWidth="0.5" />
          <line x1="120" y1="180" x2="160" y2="180" stroke="var(--accent-cyan)" strokeWidth="0.5" />
          <line x1="240" y1="180" x2="280" y2="180" stroke="var(--accent-cyan)" strokeWidth="0.5" />
        </g>
      )}

      {/* Connections */}
      <g transform={`translate(${parallaxX * 0.4}, ${parallaxY * 0.4})`}>
        {CONNECTIONS.map(([a, b], i) => {
          const la = LANDMARKS[a];
          const lb = LANDMARKS[b];
          const show = stage === "detect" || stage === "verify" || stage === "decide" || stage === "authorize";
          return (
            <line
              key={i}
              x1={la.x} y1={la.y}
              x2={lb.x} y2={lb.y}
              stroke="var(--accent-cyan)"
              strokeWidth="0.5"
              opacity={show ? 0.3 : 0}
              style={{ transition: "opacity 0.8s ease" }}
            />
          );
        })}
      </g>

      {/* Landmark nodes */}
      <g transform={`translate(${parallaxX * 0.5}, ${parallaxY * 0.5})`}>
        {LANDMARKS.map((lm, i) => {
          const show = stage === "detect" || stage === "verify" || stage === "decide" || stage === "authorize";
          const delay = i * 0.1;
          return (
            <g key={i}>
              <circle
                cx={lm.x} cy={lm.y}
                r={show ? 3 : 1.5}
                fill={show ? "var(--accent-cyan)" : "#444"}
                opacity={show ? 0.9 : 0.3}
                style={{
                  transition: `all 0.6s ease ${delay}s`,
                  filter: show ? "url(#glow)" : "none",
                }}
              />
              {show && (
                <circle
                  cx={lm.x} cy={lm.y}
                  r="6"
                  fill="none"
                  stroke="var(--accent-cyan)"
                  strokeWidth="0.5"
                  opacity="0.3"
                  style={{ animation: `eg-pulse 3s ease-in-out ${delay}s infinite` }}
                />
              )}
            </g>
          );
        })}
      </g>

      {/* Scan line */}
      {(stage === "detect" || stage === "verify") && (
        <rect
          x="100" y={scanY} width="200" height="2"
          fill="url(#scan-grad)"
          opacity="0.8"
        />
      )}

      {/* Coordinate labels */}
      {isActive && (
        <g style={{ fontFamily: "var(--font-mono), monospace", fontSize: "8px", fill: "var(--text-tertiary)" }}>
          <text x="105" y="35">x:0 y:0</text>
          <text x="280" y="35">x:400</text>
          <text x="105" y="325">x:0 y:360</text>
          <text x="265" y="325">x:400 y:360</text>
          {stage === "detect" && (
            <>
              <text x="105" y={scanY - 5}>scan: {Math.round(scanY)}</text>
              <text x="250" y={scanY - 5}>active</text>
            </>
          )}
        </g>
      )}

      {/* Stage-specific overlays */}
      {stage === "verify" && (
        <g opacity="0.4" transform={`translate(${parallaxX * 0.2}, ${parallaxY * 0.2})`}>
          <rect x="110" y="140" width="80" height="30" rx="4" fill="none" stroke="var(--accent-cyan)" strokeWidth="0.5" />
          <text x="115" y="158" style={{ fontSize: "7px", fill: "var(--accent-cyan)", fontFamily: "var(--font-mono), monospace" }}>IDENTITY</text>
          <rect x="210" y="140" width="80" height="30" rx="4" fill="none" stroke="var(--accent-emerald)" strokeWidth="0.5" />
          <text x="215" y="158" style={{ fontSize: "7px", fill: "var(--accent-emerald)", fontFamily: "var(--font-mono), monospace" }}>CONTEXT</text>
          <line x1="190" y1="155" x2="210" y2="155" stroke="var(--text-tertiary)" strokeWidth="0.5" strokeDasharray="2 2" />
        </g>
      )}

      {stage === "decide" && (
        <g opacity="0.5">
          <rect x="130" y="310" width="140" height="36" rx="6" fill="var(--surface-raised)" stroke="var(--accent-cyan)" strokeWidth="0.5" />
          <text x="140" y="325" style={{ fontSize: "7px", fill: "var(--text-tertiary)", fontFamily: "var(--font-mono), monospace" }}>EVIDENCE</text>
          <text x="140" y="338" style={{ fontSize: "8px", fill: "var(--accent-cyan)", fontFamily: "var(--font-mono), monospace" }}>→ DECISION ENGINE</text>
        </g>
      )}

      {stage === "authorize" && (
        <g opacity="0.6">
          <rect x="140" y="310" width="120" height="36" rx="6" fill="var(--surface-raised)" stroke="var(--accent-amber)" strokeWidth="0.5" />
          <text x="150" y="332" style={{ fontSize: "8px", fill: "var(--accent-amber)", fontFamily: "var(--font-mono), monospace" }}>AWAITING DECISION</text>
        </g>
      )}
    </svg>
  );
}
