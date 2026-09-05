"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MonitoringEvent } from "@/lib/monitoring-api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ConnectionStatus =
  | "INITIALIZING"
  | "CONNECTING"
  | "CONNECTED"
  | "DISCONNECTED"
  | "RECONNECTING"
  | "ERROR";

const MAX_DISPLAY_EVENTS = 200;
const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30000;

interface UseMonitoringSocketOptions {
  examId?: number;
  hallId?: number;
  category?: string;
  eventType?: string;
  minSeverity?: string;
  onEvent?: (event: MonitoringEvent) => void;
}

export function useMonitoringSocket(opts: UseMonitoringSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>("INITIALIZING");
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const buildWsUrl = useCallback(() => {
    const base = API.replace(/^http/, "ws");
    const sp = new URLSearchParams();
    if (optsRef.current.examId) sp.set("exam_id", String(optsRef.current.examId));
    if (optsRef.current.hallId) sp.set("hall_id", String(optsRef.current.hallId));
    if (optsRef.current.category) sp.set("category", optsRef.current.category);
    if (optsRef.current.eventType) sp.set("event_type", optsRef.current.eventType);
    if (optsRef.current.minSeverity) sp.set("min_severity", optsRef.current.minSeverity);
    const qs = sp.toString();
    return `${base}/api/v1/ws/monitoring${qs ? `?${qs}` : ""}`;
  }, []);

  const addEvent = useCallback((evt: MonitoringEvent) => {
    setEvents((prev) => {
      const exists = prev.some((e) => e.event_id === evt.event_id);
      if (exists) return prev;
      const next = [evt, ...prev];
      if (next.length > MAX_DISPLAY_EVENTS) next.length = MAX_DISPLAY_EVENTS;
      return next;
    });
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const existing = wsRef.current;
    if (existing) {
      try { existing.close(1000); } catch { /* ignore */ }
      wsRef.current = null;
    }

    setStatus((prev) =>
      prev === "INITIALIZING" ? "CONNECTING" : "RECONNECTING"
    );

    let ws: WebSocket;
    try {
      ws = new WebSocket(buildWsUrl());
    } catch {
      setStatus("ERROR");
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectAttempts.current = 0;
      setStatus("CONNECTED");
    };

    ws.onmessage = (msg) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(msg.data as string);
        if (data.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
          return;
        }
        if (data.type === "connected" || data.type === "subscribed") return;
        if (data.type === "error") return;
        if (data.event_id) {
          addEvent(data as MonitoringEvent);
          optsRef.current.onEvent?.(data as MonitoringEvent);
        }
      } catch {
        // malformed message — ignore
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      setStatus("DISCONNECTED");
      scheduleReconnect();
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setStatus("ERROR");
    };
  }, [buildWsUrl, addEvent]);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
      setStatus("ERROR");
      return;
    }
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current),
      MAX_RECONNECT_DELAY,
    );
    reconnectAttempts.current += 1;
    reconnectTimer.current = setTimeout(() => {
      reconnectTimer.current = null;
      connect();
    }, delay);
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    const ws = wsRef.current;
    if (ws) {
      try { ws.close(1000); } catch { /* ignore */ }
      wsRef.current = null;
    }
  }, []);

  const updateFilters = useCallback(
    (filters: {
      examId?: number;
      hallId?: number;
      category?: string;
      eventType?: string;
      minSeverity?: string;
    }) => {
      optsRef.current = { ...optsRef.current, ...filters };
      disconnect();
      reconnectAttempts.current = 0;
      connect();
    },
    [connect, disconnect],
  );

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    status,
    events,
    setEvents,
    updateFilters,
    reconnect: () => {
      reconnectAttempts.current = 0;
      connect();
    },
    disconnect,
  };
}
