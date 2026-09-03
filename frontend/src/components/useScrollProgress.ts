"use client";

import { useRef, useEffect, useCallback } from "react";

export interface ScrollState {
  progress: number;
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  subProgress: number;
  stageIndex: number;
}

const STAGE_RANGES: { stage: ScrollState["stage"]; start: number; end: number }[] = [
  { stage: "ready", start: 0, end: 0.05 },
  { stage: "detect", start: 0.05, end: 0.3 },
  { stage: "verify", start: 0.3, end: 0.55 },
  { stage: "decide", start: 0.55, end: 0.8 },
  { stage: "authorize", start: 0.8, end: 1.0 },
];

function getStageFromProgress(progress: number): ScrollState {
  for (let i = 0; i < STAGE_RANGES.length; i++) {
    const r = STAGE_RANGES[i];
    if (progress >= r.start && progress < r.end) {
      const range = r.end - r.start;
      const subProgress = range > 0 ? (progress - r.start) / range : 0;
      return { progress, stage: r.stage, subProgress, stageIndex: i };
    }
  }
  const last = STAGE_RANGES[STAGE_RANGES.length - 1];
  return {
    progress,
    stage: last.stage,
    subProgress: 1,
    stageIndex: STAGE_RANGES.length - 1,
  };
}

export function useScrollProgress(ref: React.RefObject<HTMLElement | null>) {
  const stateRef = useRef<ScrollState>({ progress: 0, stage: "ready", subProgress: 0, stageIndex: 0 });
  const callbacksRef = useRef<((state: ScrollState) => void)[]>([]);
  const rafRef = useRef<number>(0);
  const targetRef = useRef(0);
  const currentRef = useRef(0);

  const subscribe = useCallback((cb: (state: ScrollState) => void) => {
    callbacksRef.current.push(cb);
    return () => {
      callbacksRef.current = callbacksRef.current.filter((c) => c !== cb);
    };
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onScroll = () => {
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const total = rect.height - vh;
      const scrolled = -rect.top;
      targetRef.current = Math.max(0, Math.min(1, scrolled / total));
    };

    const tick = () => {
      const diff = targetRef.current - currentRef.current;
      currentRef.current += diff * 0.12;

      if (Math.abs(diff) < 0.0001) {
        currentRef.current = targetRef.current;
      }

      const state = getStageFromProgress(currentRef.current);
      stateRef.current = state;
      callbacksRef.current.forEach((cb) => cb(state));
      rafRef.current = requestAnimationFrame(tick);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(rafRef.current);
    };
  }, [ref]);

  return { subscribe, getState: () => stateRef.current };
}
