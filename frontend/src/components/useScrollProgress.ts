"use client";

import { useRef, useEffect, useCallback } from "react";

interface ScrollState {
  progress: number;
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
}

export function useScrollProgress(ref: React.RefObject<HTMLElement | null>) {
  const stateRef = useRef<ScrollState>({ progress: 0, stage: "ready" });
  const callbacksRef = useRef<((state: ScrollState) => void)[]>([]);

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
      const progress = Math.max(0, Math.min(1, scrolled / total));

      let stage: ScrollState["stage"] = "ready";
      if (progress >= 0.8) stage = "authorize";
      else if (progress >= 0.55) stage = "decide";
      else if (progress >= 0.3) stage = "verify";
      else if (progress >= 0.05) stage = "detect";

      stateRef.current = { progress, stage };
      callbacksRef.current.forEach((cb) => cb(stateRef.current));
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [ref]);

  return { subscribe, getState: () => stateRef.current };
}
