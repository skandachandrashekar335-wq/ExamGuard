"use client";

interface FaceGeometryProps {
  phase?: "frame" | "connect" | "nodes" | "scan" | "evidence" | "authorize" | "deconstruct";
  parallaxStrength?: number;
}

const NODES: [number, number][] = [
  [150, 75],
  [210, 120],
  [150, 165],
  [90, 120],
  [120, 95],
  [180, 95],
  [150, 130],
  [135, 110],
  [165, 110],
  [150, 100],
];

const CONNECTIONS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 0],
  [4, 8], [5, 7], [4, 7], [5, 8],
  [9, 6], [6, 0], [6, 2],
];

export default function FaceGeometry({ phase = "frame", parallaxStrength = 0.02 }: FaceGeometryProps) {
  const showFrame = phase !== "authorize";
  const showNodes = phase === "nodes" || phase === "connect" || phase === "scan" || phase === "evidence" || phase === "authorize";
  const showConnections = phase === "connect" || phase === "scan" || phase === "evidence" || phase === "authorize";
  const showScan = phase === "scan" || phase === "evidence" || phase === "authorize";
  const showEyes = phase === "evidence" || phase === "authorize";
  const isAuthorize = phase === "authorize";

  const parallaxMultiplier = parallaxStrength * 1000;

  return (
    <div className="relative w-[200px] h-[200px] sm:w-[240px] sm:h-[240px]">
      <svg
        viewBox="0 0 300 240"
        className="w-full h-full"
        style={{
          transform: `translate(calc(var(--mouse-x, 0) * ${parallaxMultiplier}px), calc(var(--mouse-y, 0) * ${parallaxMultiplier}px))`,
          transition: "transform 0.1s ease-out",
        }}
      >
        {/* Outer frame — hexagon approximation */}
        {showFrame && (
          <g opacity={isAuthorize ? 0.15 : 0.25}>
            <polygon
              points="150,20 230,60 230,180 150,220 70,180 70,60"
              fill="none"
              stroke="var(--accent-cyan)"
              strokeWidth="1"
              strokeDasharray={isAuthorize ? "none" : "6 4"}
              style={{ transition: "all 0.6s ease-out" }}
            />
            {/* Inner hexagon */}
            <polygon
              points="150,40 210,70 210,170 150,200 90,170 90,70"
              fill="none"
              stroke="var(--accent-cyan)"
              strokeWidth="0.5"
              strokeDasharray="3 3"
              opacity={0.15}
            />
            {/* Dimensional lines */}
            <line x1="70" y1="120" x2="230" y2="120" stroke="var(--accent-cyan)" strokeWidth="0.3" opacity={0.1} strokeDasharray="2 4" />
            <line x1="150" y1="20" x2="150" y2="220" stroke="var(--accent-cyan)" strokeWidth="0.3" opacity={0.1} strokeDasharray="2 4" />
          </g>
        )}

        {/* Scan line — CSS animation */}
        {showScan && (
          <rect
            x="60"
            y="30"
            width="180"
            height="3"
            rx="1.5"
            fill="var(--accent-cyan)"
            opacity={0.6}
            className={isAuthorize ? "" : "eg-scan-line"}
            style={isAuthorize ? {
              y: 120,
              opacity: 0.2,
              transition: "all 0.8s ease-out",
            } : {}}
          />
        )}

        {/* Evidence particles */}
        {phase === "evidence" && (
          <g>
            {[...Array(12)].map((_, i) => {
              const angle = (i / 12) * Math.PI * 2;
              const r = 55 + Math.sin(i * 1.7) * 15;
              const px = 150 + Math.cos(angle) * r;
              const py = 120 + Math.sin(angle) * r;
              return (
                <circle
                  key={i}
                  cx={px}
                  cy={py}
                  r={1.5}
                  fill="var(--accent-amber)"
                  opacity={0.4 + (i % 3) * 0.15}
                  className="eg-evidence-particle"
                  style={{ animationDelay: `${i * 0.12}s` }}
                />
              );
            })}
            {/* Converging lines */}
            {[...Array(6)].map((_, i) => {
              const angle = (i / 6) * Math.PI * 2;
              const r = 60;
              const px = 150 + Math.cos(angle) * r;
              const py = 120 + Math.sin(angle) * r;
              return (
                <line
                  key={`line-${i}`}
                  x1={px}
                  y1={py}
                  x2="150"
                  y2="120"
                  stroke="var(--accent-amber)"
                  strokeWidth="0.4"
                  opacity={0.15}
                  strokeDasharray="2 3"
                />
              );
            })}
          </g>
        )}

        {/* Connections */}
        {showConnections && (
          <g>
            {CONNECTIONS.map(([a, b], i) => (
              <line
                key={`conn-${i}`}
                x1={NODES[a][0]}
                y1={NODES[a][1]}
                x2={NODES[b][0]}
                y2={NODES[b][1]}
                stroke={isAuthorize ? "var(--accent-emerald)" : "var(--accent-cyan)"}
                strokeWidth="0.8"
                opacity={0.3}
                strokeDasharray={isAuthorize ? "none" : "3 2"}
                style={{ transition: "stroke 0.4s, opacity 0.4s" }}
              />
            ))}
          </g>
        )}

        {/* Nodes */}
        {showNodes && (
          <g>
            {NODES.map(([x, y], i) => (
              <g key={`node-${i}`} className="eg-face-node" style={{ animationDelay: `${i * 0.06}s` }}>
                {/* Outer ring */}
                <circle
                  cx={x}
                  cy={y}
                  r={4.5}
                  fill="none"
                  stroke={isAuthorize ? "var(--accent-emerald)" : "var(--accent-cyan)"}
                  strokeWidth="0.6"
                  opacity={0.4}
                  style={{ transition: "stroke 0.4s" }}
                />
                {/* Core */}
                <circle
                  cx={x}
                  cy={y}
                  r={1.8}
                  fill={isAuthorize ? "var(--accent-emerald)" : "var(--accent-cyan)"}
                  opacity={0.8}
                  style={{ transition: "fill 0.4s" }}
                />
                {/* Glow */}
                <circle
                  cx={x}
                  cy={y}
                  r={8}
                  fill={isAuthorize ? "var(--accent-emerald)" : "var(--accent-cyan)"}
                  opacity={0.04}
                />
              </g>
            ))}
          </g>
        )}

        {/* Eye indicators */}
        {showEyes && (
          <g>
            <circle cx="120" cy="95" r="12" fill="none" stroke="var(--accent-cyan)" strokeWidth="0.6" opacity={0.25} strokeDasharray="2 2" />
            <circle cx="180" cy="95" r="12" fill="none" stroke="var(--accent-cyan)" strokeWidth="0.6" opacity={0.25} strokeDasharray="2 2" />
            <circle cx="120" cy="95" r="4" fill="var(--accent-cyan)" opacity={0.06} />
            <circle cx="180" cy="95" r="4" fill="var(--accent-cyan)" opacity={0.06} />
          </g>
        )}

        {/* Authorize state — minimal + emerald */}
        {isAuthorize && (
          <g>
            {/* Central diamond */}
            <rect x="143" y="113" width="14" height="14" rx="2" fill="none" stroke="var(--accent-emerald)" strokeWidth="1.2" opacity={0.5} transform="rotate(45, 150, 120)" />
            {/* Check mark */}
            <path d="M145 120 L149 124 L156 116" stroke="var(--accent-emerald)" strokeWidth="1.5" fill="none" opacity={0.6} strokeLinecap="round" strokeLinejoin="round" />
          </g>
        )}
      </svg>
    </div>
  );
}
