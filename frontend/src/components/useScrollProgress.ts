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

function statesEqual(a: ScrollState, b: ScrollState): boolean {
  return a.progress === b.progress && a.stage === b.stage && a.subProgress === b.subProgress && a.stageIndex === b.stageIndex;
}

export function useScrollProgress(ref: React.RefObject<HTMLElement | null>) {
  const stateRef = useRef<ScrollState>({ progress: 0, stage: "ready", subProgress: 0, stageIndex: 0 });
  const callbacksRef = useRef<((state: ScrollState) => void)[]>([]);
  const rafRef = useRef<number>(0);
  const targetRef = useRef(0);
  const currentRef = useRef(0);
  const tickingRef = useRef(false);
  const scrollFrameRef = useRef<number>(0);

  const subscribe = useCallback((cb: (state: ScrollState) => void) => {
    callbacksRef.current.push(cb);
    return () => {
      callbacksRef.current = callbacksRef.current.filter((c) => c !== cb);
    };
  }, []);

  // RAF loop — terminates when converged
  const tick = useCallback(() => {
    const diff = targetRef.current - currentRef.current;

    if (Math.abs(diff) < 0.0001) {
      currentRef.current = targetRef.current;
      const state = getStageFromProgress(currentRef.current);
      if (!statesEqual(state, stateRef.current)) {
        stateRef.current = state;
        callbacksRef.current.forEach((cb) => cb(state));
      }
      tickingRef.current = false;
      return;
    }

    currentRef.current += diff * 0.1;

    const state = getStageFromProgress(currentRef.current);
    if (!statesEqual(state, stateRef.current)) {
      stateRef.current = state;
      callbacksRef.current.forEach((cb) => cb(state));
    }

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const startTicking = useCallback(() => {
    if (!tickingRef.current) {
      tickingRef.current = true;
      rafRef.current = requestAnimationFrame(tick);
    }
  }, [tick]);

  // RAF-gated scroll handler — only one getBoundingClientRect per frame
  const onScroll = useCallback(() => {
    if (scrollFrameRef.current) return;
    scrollFrameRef.current = requestAnimationFrame(() => {
      scrollFrameRef.current = 0;
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const total = rect.height - vh;
      if (total <= 0) return;
      const scrolled = -rect.top;
      targetRef.current = Math.max(0, Math.min(1, scrolled / total));
      startTicking();
    });
  }, [ref, startTicking]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(rafRef.current);
      cancelAnimationFrame(scrollFrameRef.current);
    };
  }, [ref, onScroll]);

  return { subscribe, getState: () => stateRef.current };
}

/**
 * CSS-variable mouse tracking.
 * Updates --mouse-x / --mouse-y on document root via RAF.
 * Loop terminates when mouse stops moving.
 */
export function useMouseCSS() {
  const targetRef = useRef({ x: 0, y: 0 });
  const currentRef = useRef({ x: 0, y: 0 });
  const rafRef = useRef<number>(0);
  const tickingRef = useRef(false);

  const tick = useCallback(() => {
    const dx = targetRef.current.x - currentRef.current.x;
    const dy = targetRef.current.y - currentRef.current.y;

    if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) {
      currentRef.current.x = targetRef.current.x;
      currentRef.current.y = targetRef.current.y;
      document.documentElement.style.setProperty("--mouse-x", String(currentRef.current.x));
      document.documentElement.style.setProperty("--mouse-y", String(currentRef.current.y));
      tickingRef.current = false;
      return;
    }

    currentRef.current.x += dx * 0.08;
    currentRef.current.y += dy * 0.08;

    document.documentElement.style.setProperty("--mouse-x", String(currentRef.current.x));
    document.documentElement.style.setProperty("--mouse-y", String(currentRef.current.y));

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const startTicking = useCallback(() => {
    if (!tickingRef.current) {
      tickingRef.current = true;
      rafRef.current = requestAnimationFrame(tick);
    }
  }, [tick]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      targetRef.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      targetRef.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
      startTicking();
    };

    const onLeave = () => {
      targetRef.current.x = 0;
      targetRef.current.y = 0;
      startTicking();
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseleave", onLeave, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseleave", onLeave);
      cancelAnimationFrame(rafRef.current);
    };
  }, [startTicking]);
}
