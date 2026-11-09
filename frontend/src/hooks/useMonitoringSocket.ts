"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MonitoringEvent } from "@/lib/monitoring-api";
import { API_BASE, getAuthToken } from "@/lib/api";

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
  const connectingRef = useRef(false);
  const optsRef = useRef(opts);
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => {
    optsRef.current = opts;
  }, [opts]);

  const buildWsUrl = useCallback(() => {
    const base = API_BASE.replace(/^http/, "ws");
    const sp = new URLSearchParams();
    const token = getAuthToken();
    if (token) sp.set("token", token);
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
      connectRef.current();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (connectingRef.current) return;
    connectingRef.current = true;

    const existing = wsRef.current;
    if (existing) {
      try { existing.close(1000); } catch { /* ignore */ }
      wsRef.current = null;
    }

    let ws: WebSocket;
    try {
      ws = new WebSocket(buildWsUrl());
    } catch {
      connectingRef.current = false;
      setStatus("ERROR");
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    queueMicrotask(() => {
      if (mountedRef.current) {
        setStatus((prev) =>
          prev === "INITIALIZING" ? "CONNECTING" : "RECONNECTING"
        );
      }
    });

    ws.onopen = () => {
      if (!mountedRef.current) return;
      connectingRef.current = false;
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
      connectingRef.current = false;
      wsRef.current = null;
      setStatus("DISCONNECTED");
      scheduleReconnect();
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      connectingRef.current = false;
      setStatus("ERROR");
    };
  }, [buildWsUrl, addEvent, scheduleReconnect]);

  useEffect(() => {
    connectRef.current = connect;
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
    const timer = setTimeout(() => {
      connect();
    }, 0);
    return () => {
      mountedRef.current = false;
      clearTimeout(timer);
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
