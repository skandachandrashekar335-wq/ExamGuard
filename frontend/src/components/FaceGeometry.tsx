"use client";

import { useRef, useEffect, useState } from "react";

interface FaceGeometryProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  progress: number;
  subProgress: number;
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

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v));
}

function mapRange(value: number, inMin: number, inMax: number, outMin: number, outMax: number) {
  return clamp(outMin + ((value - inMin) / (inMax - inMin)) * (outMax - outMin), Math.min(outMin, outMax), Math.max(outMin, outMax));
}

export default function FaceGeometry({ stage, progress, subProgress, mouseX, mouseY }: FaceGeometryProps) {
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

  const p = progress;
  const sp = subProgress;

  // Frame opacity: appears 0-10% progress
  const frameOpacity = mapRange(p, 0.02, 0.1, 0, 0.6);
  const frameStroke = mapRange(p, 0.02, 0.1, 0.5, 1.5);
  const frameDash = p < 0.08 ? "4 4" : "none";

  // Grid opacity: intensifies with progress
  const gridOpacity = mapRange(p, 0, 0.15, 0.03, 0.18);

  // Crosshair: appears at 8%
  const crosshairOpacity = mapRange(p, 0.06, 0.12, 0, 0.25);

  // Landmark nodes: progressive reveal 12%-30%
  const nodeVisibility = (i: number) => {
    const stagger = i * 0.008;
    return mapRange(p, 0.12 + stagger, 0.2 + stagger, 0, 1);
  };

  // Connections: progressive reveal 18%-38%
  const connectionVisibility = (i: number) => {
    const stagger = (i / CONNECTIONS.length) * 0.1;
    return mapRange(p, 0.18 + stagger, 0.3 + stagger, 0, 1);
  };

  // Scan line: active during detect 20%-50%, verify 50%-70%
  const scanActive = p > 0.2 && p < 0.7;
  const scanY = (time * 40) % 360;
  const scanOpacity = scanActive ? mapRange(p, 0.2, 0.3, 0, 0.8) * mapRange(p, 0.6, 0.7, 0.8, 0) : 0;

  // Verify overlays: appear at 35%-55%
  const verifyOverlayOpacity = mapRange(p, 0.35, 0.45, 0, 0.5) * mapRange(p, 0.55, 0.65, 0.5, 0);

  // Decide: deconstruct 55%-70%, evidence converge 70%-80%
  const deconstructAmount = mapRange(p, 0.55, 0.7, 0, 1);
  const evidenceConverge = mapRange(p, 0.7, 0.82, 0, 1);

  // Authorize: simplify 80%-100%
  const authorizeOpacity = mapRange(p, 0.82, 0.92, 0, 0.7);

  // Overall geometry opacity: dormant early, active middle, simplified late
  const geometryOverallOpacity = p < 0.05 ? 0.15 : p < 0.85 ? 1 : mapRange(p, 0.85, 1, 1, 0.5);

  // Parallax depth layers
  const parallaxX = mouseX * 10;
  const parallaxY = mouseY * 6;

  // Deconstruct effect: nodes drift apart during decide
  const deconstructNode = (x: number, y: number, i: number) => {
    if (deconstructAmount <= 0) return { x, y };
    const cx = 200, cy = 180;
    const dx = (x - cx) * deconstructAmount * 0.3;
    const dy = (y - cy) * deconstructAmount * 0.3;
    return { x: x + dx, y: y + dy };
  };

  // Evidence particle positions during decide
  const evidenceParticleX = (i: number) => {
    const baseX = 50 + (i * 30) % 300;
    const targetX = 200;
    return baseX + (targetX - baseX) * evidenceConverge;
  };
  const evidenceParticleY = (i: number) => {
    const baseY = 100 + (i * 25) % 200;
    const targetY = 320;
    return baseY + (targetY - baseY) * evidenceConverge;
  };

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 400 360"
      className="w-full h-full max-w-[500px] mx-auto"
      style={{ filter: p < 0.02 ? "grayscale(0.5) opacity(0.15)" : "none" }}
    >
      <defs>
        <radialGradient id="face-glow" cx="50%" cy="45%" r="45%">
          <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0.1" />
          <stop offset="100%" stopColor="transparent" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="scan-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0" />
          <stop offset="50%" stopColor="var(--accent-cyan)" stopOpacity="0.7" />
          <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="glow-strong">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* LAYER 1: Background grid — parallax layer 0.1 */}
      <g opacity={gridOpacity} transform={`translate(${parallaxX * 0.1}, ${parallaxY * 0.1})`}>
        {Array.from({ length: 19 }, (_, i) => (
          <line key={`v${i}`} x1={i * 20} y1={0} x2={i * 20} y2={360} stroke="var(--accent-cyan)" strokeWidth="0.5" />
        ))}
        {Array.from({ length: 19 }, (_, i) => (
          <line key={`h${i}`} x1={0} y1={i * 20} x2={400} y2={i * 20} stroke="var(--accent-cyan)" strokeWidth="0.5" />
        ))}
      </g>

      {/* Face glow */}
      <circle cx="200" cy="180" r="140" fill="url(#face-glow)" opacity={geometryOverallOpacity} />

      {/* LAYER 2: Technical labels — parallax layer 0.15 */}
      <g opacity={crosshairOpacity * 0.6} style={{ fontFamily: "var(--font-mono), monospace", fontSize: "7px", fill: "var(--text-tertiary)" }} transform={`translate(${parallaxX * 0.15}, ${parallaxY * 0.15})`}>
        <text x="105" y="35">x:0 y:0</text>
        <text x="280" y="35">x:400</text>
        <text x="105" y="330">x:0 y:360</text>
        <text x="265" y="330">x:400 y:360</text>
        {scanActive && (
          <text x="105" y={scanY - 5} opacity={scanOpacity}>
            scan: {Math.round(scanY)}
          </text>
        )}
      </g>

      {/* LAYER 3: Outer frame — parallax layer 0.2 */}
      <rect
        x="100" y="40" width="200" height="280" rx="16"
        fill="none"
        stroke={p > 0.05 ? "var(--accent-cyan)" : "#333"}
        strokeWidth={frameStroke}
        strokeDasharray={frameDash}
        opacity={frameOpacity}
        transform={`translate(${parallaxX * 0.2}, ${parallaxY * 0.2})`}
      />

      {/* Crosshair — parallax layer 0.15 */}
      <g opacity={crosshairOpacity} transform={`translate(${parallaxX * 0.15}, ${parallaxY * 0.15})`}>
        <line x1="200" y1="55" x2="200" y2="95" stroke="var(--accent-cyan)" strokeWidth="0.5" />
        <line x1="200" y1="265" x2="200" y2="305" stroke="var(--accent-cyan)" strokeWidth="0.5" />
        <line x1="115" y1="180" x2="155" y2="180" stroke="var(--accent-cyan)" strokeWidth="0.5" />
        <line x1="245" y1="180" x2="285" y2="180" stroke="var(--accent-cyan)" strokeWidth="0.5" />
        <circle cx="200" cy="180" r="3" fill="none" stroke="var(--accent-cyan)" strokeWidth="0.5" />
      </g>

      {/* LAYER 4: Connections — parallax layer 0.3 */}
      <g transform={`translate(${parallaxX * 0.3}, ${parallaxY * 0.3})`}>
        {CONNECTIONS.map(([a, b], i) => {
          const la = LANDMARKS[a];
          const lb = LANDMARKS[b];
          const vis = connectionVisibility(i);
          const da = deconstructNode(la.x, la.y, a);
          const db = deconstructNode(lb.x, lb.y, b);
          return (
            <line
              key={i}
              x1={da.x} y1={da.y}
              x2={db.x} y2={db.y}
              stroke="var(--accent-cyan)"
              strokeWidth="0.5"
              opacity={vis * 0.35 * geometryOverallOpacity}
            />
          );
        })}
      </g>

      {/* LAYER 5: Landmark nodes — parallax layer 0.4 */}
      <g transform={`translate(${parallaxX * 0.4}, ${parallaxY * 0.4})`}>
        {LANDMARKS.map((lm, i) => {
          const vis = nodeVisibility(i);
          const pos = deconstructNode(lm.x, lm.y, i);
          return (
            <g key={i}>
              <circle
                cx={pos.x} cy={pos.y}
                r={vis > 0.5 ? 3 : 1.5}
                fill={vis > 0.3 ? "var(--accent-cyan)" : "#444"}
                opacity={vis * geometryOverallOpacity}
                filter={vis > 0.5 ? "url(#glow)" : "none"}
              />
              {vis > 0.7 && (
                <circle
                  cx={pos.x} cy={pos.y}
                  r="7"
                  fill="none"
                  stroke="var(--accent-cyan)"
                  strokeWidth="0.5"
                  opacity={vis * 0.2 * geometryOverallOpacity}
                />
              )}
            </g>
          );
        })}
      </g>

      {/* LAYER 5b: Scan line — parallax layer 0.35 */}
      {scanActive && (
        <rect
          x="100" y={scanY} width="200" height="2"
          fill="url(#scan-grad)"
          opacity={scanOpacity}
          transform={`translate(${parallaxX * 0.35}, 0)`}
        />
      )}

      {/* Verify overlay: IDENTITY + CONTEXT — parallax layer 0.25 */}
      {verifyOverlayOpacity > 0.01 && (
        <g opacity={verifyOverlayOpacity} transform={`translate(${parallaxX * 0.25}, ${parallaxY * 0.25})`}>
          {/* IDENTITY box */}
          <rect x="80" y="130" width="90" height="35" rx="4" fill="var(--surface)" stroke="var(--accent-cyan)" strokeWidth="0.5" />
          <text x="87" y="150" style={{ fontSize: "7px", fill: "var(--accent-cyan)", fontFamily: "var(--font-mono), monospace" }}>IDENTITY</text>
          <text x="87" y="158" style={{ fontSize: "5px", fill: "var(--text-tertiary)", fontFamily: "var(--font-mono), monospace" }}>face detected</text>

          {/* CONTEXT box */}
          <rect x="230" y="130" width="90" height="35" rx="4" fill="var(--surface)" stroke="var(--accent-emerald)" strokeWidth="0.5" />
          <text x="237" y="150" style={{ fontSize: "7px", fill: "var(--accent-emerald)", fontFamily: "var(--font-mono), monospace" }}>CONTEXT</text>
          <text x="237" y="158" style={{ fontSize: "5px", fill: "var(--text-tertiary)", fontFamily: "var(--font-mono), monospace" }}>hall ticket</text>

          {/* Connection arrows */}
          <line x1="170" y1="147" x2="195" y2="147" stroke="var(--text-tertiary)" strokeWidth="0.5" strokeDasharray="2 2" />
          <polygon points="195,144 201,147 195,150" fill="var(--text-tertiary)" />

          {/* Convergence line down */}
          <line x1="200" y1="165" x2="200" y2={185 + (1 - sp) * 20} stroke="var(--accent-cyan)" strokeWidth="0.5" opacity="0.4" />
        </g>
      )}

      {/* Decide: evidence particles — parallax layer 0.2 */}
      {p >= 0.55 && p <= 0.85 && (
        <g opacity={mapRange(p, 0.55, 0.65, 0, 1) * mapRange(p, 0.8, 0.85, 1, 0)} transform={`translate(${parallaxX * 0.2}, ${parallaxY * 0.2})`}>
          {Array.from({ length: 8 }, (_, i) => {
            const ex = evidenceParticleX(i);
            const ey = evidenceParticleY(i);
            return (
              <g key={`ev-${i}`}>
                <circle cx={ex} cy={ey} r={2 + evidenceConverge} fill="var(--accent-cyan)" opacity={0.6 + evidenceConverge * 0.4} />
                <line x1={ex} y1={ey} x2={200} y2={320} stroke="var(--accent-cyan)" strokeWidth="0.3" opacity={evidenceConverge * 0.3} />
              </g>
            );
          })}

          {/* Decision engine node */}
          <circle cx="200" cy={320} r={6 + evidenceConverge * 4} fill="var(--surface)" stroke="var(--accent-emerald)" strokeWidth={0.5 + evidenceConverge} opacity={evidenceConverge * 0.8} />
          <text x="200" y={323} textAnchor="middle" style={{ fontSize: "5px", fill: "var(--accent-emerald)", fontFamily: "var(--font-mono), monospace" }} opacity={evidenceConverge}>
            ENGINE
          </text>
        </g>
      )}

      {/* Authorize: awaiting decision — parallax layer 0.2 */}
      {authorizeOpacity > 0.01 && (
        <g opacity={authorizeOpacity} transform={`translate(${parallaxX * 0.2}, ${parallaxY * 0.2})`}>
          <rect x="130" y="300" width="140" height="40" rx="6" fill="var(--surface)" stroke="var(--accent-amber)" strokeWidth="0.5" />
          <text x="200" y="318" textAnchor="middle" style={{ fontSize: "7px", fill: "var(--accent-amber)", fontFamily: "var(--font-mono), monospace" }}>
            AWAITING
          </text>
          <text x="200" y="330" textAnchor="middle" style={{ fontSize: "6px", fill: "var(--text-tertiary)", fontFamily: "var(--font-mono), monospace" }}>
            VERIFIED DECISION
          </text>
        </g>
      )}
    </svg>
  );
}
