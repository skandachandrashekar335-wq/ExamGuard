"use client";

import React from "react";

interface FaceGeometryProps {
  phase: "frame" | "scan" | "evidence" | "authorize";
  className?: string;
}

const NODES: [number, number][] = [
  [150, 65],
  [200, 105],
  [200, 155],
  [150, 195],
  [100, 155],
  [100, 105],
  [130, 90],
  [170, 90],
  [150, 130],
  [130, 145],
  [170, 145],
];

const EDGES: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0],
  [6, 7], [8, 9], [8, 10],
  [0, 6], [0, 7], [3, 9], [3, 10],
];

function FaceGeometryInner({ phase, className = "" }: FaceGeometryProps) {
  const showFrame = phase === "frame" || phase === "scan" || phase === "evidence" || phase === "authorize";
  const showScan = phase === "scan" || phase === "evidence" || phase === "authorize";
  const showEvidence = phase === "evidence";
  const isAuthorize = phase === "authorize";

  return (
    <div
      className={`relative ${className}`}
      style={{
        transform: "translate(calc(var(--mouse-x, 0) * 6px), calc(var(--mouse-y, 0) * 6px))",
        transition: "transform 0.15s ease-out",
      }}
    >
      <svg viewBox="0 0 300 260" className="w-full h-full" fill="none">
        {/* Outer registration frame */}
        {showFrame && (
          <g opacity={0.3}>
            {/* Hexagonal boundary */}
            <polygon
              points="150,15 240,60 240,200 150,245 60,200 60,60"
              stroke="var(--white)"
              strokeWidth="0.5"
              strokeDasharray={isAuthorize ? "none" : "4 3"}
              style={{ transition: "all 0.5s ease-out" }}
            />
            {/* Inner boundary */}
            <polygon
              points="150,35 220,70 220,190 150,225 80,190 80,70"
              stroke="var(--white)"
              strokeWidth="0.3"
              strokeDasharray="2 4"
              opacity={0.2}
            />
            {/* Cross-hairs */}
            <line x1="60" y1="130" x2="240" y2="130" stroke="var(--white)" strokeWidth="0.2" opacity={0.1} strokeDasharray="1 3" />
            <line x1="150" y1="15" x2="150" y2="245" stroke="var(--white)" strokeWidth="0.2" opacity={0.1} strokeDasharray="1 3" />
          </g>
        )}

        {/* Scan line — CSS animated */}
        {showScan && (
          <g className={isAuthorize ? "" : "eg-scan-line"}>
            <line x1="70" y1="0" x2="230" y2="0" stroke="var(--white)" strokeWidth="0.5" opacity={0.5} />
            <line x1="90" y1="0" x2="210" y2="0" stroke="var(--white)" strokeWidth="1.5" opacity={0.15} />
          </g>
        )}

        {/* Edges */}
        <g opacity={0.2}>
          {EDGES.map(([a, b], i) => (
            <line
              key={`e-${i}`}
              x1={NODES[a][0]} y1={NODES[a][1]}
              x2={NODES[b][0]} y2={NODES[b][1]}
              stroke="var(--white)"
              strokeWidth="0.5"
              strokeDasharray={isAuthorize ? "none" : "2 2"}
            />
          ))}
        </g>

        {/* Nodes */}
        <g>
          {NODES.map(([x, y], i) => (
            <g key={`n-${i}`}>
              <circle cx={x} cy={y} r={3.5} stroke="var(--white)" strokeWidth="0.5" fill="none" opacity={0.4} />
              <circle cx={x} cy={y} r={1.2} fill="var(--white)" opacity={0.7} />
            </g>
          ))}
        </g>

        {/* Evidence particles */}
        {showEvidence && (
          <g>
            {[...Array(8)].map((_, i) => {
              const angle = (i / 8) * Math.PI * 2;
              const r = 50 + (i % 3) * 8;
              const px = 150 + Math.cos(angle) * r;
              const py = 130 + Math.sin(angle) * r;
              return (
                <g key={`p-${i}`}>
                  <circle cx={px} cy={py} r={1.5} fill="var(--white)" opacity={0.3} className="eg-evidence-particle" style={{ animationDelay: `${i * 0.2}s` }} />
                  <line x1={px} y1={py} x2="150" y2="130" stroke="var(--white)" strokeWidth="0.2" opacity={0.1} strokeDasharray="1 3" />
                </g>
              );
            })}
          </g>
        )}

        {/* Authorize — checkmark */}
        {isAuthorize && (
          <g opacity={0.5}>
            <rect x="140" y="118" width="20" height="20" stroke="var(--white)" strokeWidth="1" fill="none" />
            <polyline points="144,130 148,134 156,124" stroke="var(--white)" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        )}
      </svg>
    </div>
  );
}

const FaceGeometry = React.memo(FaceGeometryInner);
export default FaceGeometry;
