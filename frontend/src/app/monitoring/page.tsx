"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  getMonitoringAlerts,
  getMonitoringEvents,
  getMonitoringStatus,
  safePayload,
  type EventCategory,
  type EventSeverity,
  type EventType,
  type MonitoringAlert,
  type MonitoringEvent,
  type MonitoringStatus,
} from "@/lib/monitoring-api";
import {
  useMonitoringSocket,
  type ConnectionStatus,
} from "@/hooks/useMonitoringSocket";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EVENT_CATEGORIES: EventCategory[] = [
  "ENTRY",
  "RISK",
  "ATTENDANCE",
  "CAMERA",
  "SYSTEM",
];

const EVENT_TYPES: EventType[] = [
  "ENTRY_CREATED",
  "ENTRY_BEGAN",
  "ENTRY_GRANTED",
  "ENTRY_DENIED",
  "ENTRY_ESCALATED",
  "ENTRY_RESOLVED",
  "SIGNAL_DETECTED",
  "RISK_ASSESSED",
  "RISK_ELEVATED",
  "RISK_HIGH",
  "RISK_CRITICAL",
  "ATTENDANCE_RECORDED",
  "ATTENDANCE_CORRECTED",
  "CAMERA_ONLINE",
  "CAMERA_OFFLINE",
  "HEARTBEAT",
];

const SEVERITIES: EventSeverity[] = ["INFO", "WARNING", "CRITICAL"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function severityColor(s: EventSeverity): string {
  if (s === "CRITICAL") return "text-white";
  if (s === "WARNING") return "text-[var(--gray-300)]";
  return "text-[var(--text-muted)]";
}

function severityBorder(s: EventSeverity): string {
  if (s === "CRITICAL") return "border-l-white";
  if (s === "WARNING") return "border-l-[var(--gray-400)]";
  return "border-l-transparent";
}

function statusDot(status: ConnectionStatus): string {
  if (status === "CONNECTED") return "bg-white";
  if (status === "CONNECTING" || status === "RECONNECTING")
    return "bg-[var(--gray-500)]";
  return "bg-[var(--gray-700)]";
}

// ---------------------------------------------------------------------------
// Event Row
// ---------------------------------------------------------------------------

function EventRow({
  event,
  expanded,
  onToggle,
}: {
  event: MonitoringEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  const payload = safePayload(event.payload);
  const hasPayload = Object.keys(payload).length > 0;

  return (
    <div
      className={`border border-white/[0.06] border-l-2 ${severityBorder(event.severity)} bg-[var(--bg-surface)] transition-colors duration-150`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-4 py-3 flex items-start gap-4 eg-focusable"
        aria-expanded={expanded}
      >
        <span
          className={`eg-mono-sm mt-0.5 shrink-0 w-[5.5rem] ${severityColor(event.severity)}`}
        >
          {formatTime(event.timestamp)}
        </span>
        <span className="eg-mono-sm mt-0.5 shrink-0 w-28 text-[var(--text-secondary)]">
          {event.event_type}
        </span>
        <span className="eg-mono-sm mt-0.5 shrink-0 w-20 text-[var(--text-muted)]">
          {event.category}
        </span>
        <span className="eg-mono-sm mt-0.5 shrink-0 w-16 text-[var(--text-muted)]">
          {event.severity}
        </span>
        <span className="eg-mono-sm mt-0.5 flex-1 text-[var(--text-secondary)]">
          {event.entity_type} #{event.entity_id}
        </span>
        {event.exam_id != null && (
          <span className="eg-mono-sm mt-0.5 shrink-0 text-[var(--text-muted)]">
            EXAM {event.exam_id}
          </span>
        )}
        {event.hall_id != null && (
          <span className="eg-mono-sm mt-0.5 shrink-0 text-[var(--text-muted)]">
            HALL {event.hall_id}
          </span>
        )}
      </button>
      {expanded && (
        <div className="px-4 pb-3 border-t border-white/[0.04]">
          <div className="pt-3 grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
            <span className="eg-mono-sm text-[var(--text-muted)]">EVENT ID</span>
            <span className="eg-mono text-[var(--text-secondary)] text-xs break-all">
              {event.event_id}
            </span>
            {event.student_id != null && (
              <>
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  STUDENT
                </span>
                <span className="eg-mono text-[var(--text-secondary)]">
                  #{event.student_id}
                </span>
              </>
            )}
            {event.entry_point_id != null && (
              <>
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  ENTRY POINT
                </span>
                <span className="eg-mono text-[var(--text-secondary)]">
                  #{event.entry_point_id}
                </span>
              </>
            )}
          </div>
          {hasPayload ? (
            <div className="mt-3">
              <span className="eg-mono-sm text-[var(--text-muted)]">
                PAYLOAD
              </span>
              <pre className="mt-1 eg-mono text-xs text-[var(--text-secondary)] bg-[var(--bg-raised)] border border-white/[0.06] p-3 overflow-x-auto max-h-48">
                {JSON.stringify(payload, null, 2)}
              </pre>
            </div>
          ) : (
            <p className="mt-3 text-xs text-[var(--text-muted)] italic">
              No additional event data.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alert Row
// ---------------------------------------------------------------------------

function AlertRow({ alert }: { alert: MonitoringAlert }) {
  return (
    <div
      className={`border border-white/[0.06] border-l-2 ${severityBorder(alert.severity)} bg-[var(--bg-surface)] px-4 py-3`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`eg-mono-sm mt-0.5 shrink-0 ${severityColor(alert.severity)}`}
        >
          {alert.severity}
        </span>
        <span className="eg-mono-sm mt-0.5 flex-1 text-[var(--text-secondary)]">
          {alert.message}
        </span>
        <span className="eg-mono-sm mt-0.5 shrink-0 text-[var(--text-muted)]">
          {formatTime(alert.created_at)}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-4 text-xs">
        <span className="eg-mono-sm text-[var(--text-muted)]">
          {alert.event_type}
        </span>
        <span className="eg-mono-sm text-[var(--text-muted)]">
          {alert.entity_type} #{alert.entity_id}
        </span>
        {alert.exam_id != null && (
          <span className="eg-mono-sm text-[var(--text-muted)]">
            EXAM {alert.exam_id}
          </span>
        )}
        {alert.hall_id != null && (
          <span className="eg-mono-sm text-[var(--text-muted)]">
            HALL {alert.hall_id}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MonitoringPage() {
  // Status
  const [status, setStatus] = useState<MonitoringStatus | null>(null);
  const [statusError, setStatusError] = useState("");

  // Events
  const [restEvents, setRestEvents] = useState<MonitoringEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState("");

  // Alerts
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState("");

  // Filters
  const [filterCategory, setFilterCategory] = useState<EventCategory | "">("");
  const [filterEventType, setFilterEventType] = useState<EventType | "">("");
  const [filterSeverity, setFilterSeverity] = useState<EventSeverity | "">("");
  const [filterExamId, setFilterExamId] = useState("");
  const [filterHallId, setFilterHallId] = useState("");
  const [filterLimit, setFilterLimit] = useState("50");

  // Alert filters
  const [alertSeverity, setAlertSeverity] = useState<EventSeverity | "">("");
  const [alertEventType, setAlertEventType] = useState<EventType | "">("");
  const [alertLimit, setAlertLimit] = useState("50");

  // Expanded event
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Mounted ref for cleanup
  const mountedRef = useRef(true);

  // WebSocket
  const wsFilterArgs = useMemo(
    () => ({
      examId: filterExamId ? Number(filterExamId) : undefined,
      hallId: filterHallId ? Number(filterHallId) : undefined,
      category: filterCategory || undefined,
      eventType: filterEventType || undefined,
      minSeverity: filterSeverity || undefined,
    }),
    [filterCategory, filterEventType, filterSeverity, filterExamId, filterHallId],
  );

  const handleWsEvent = useCallback(
    (evt: MonitoringEvent) => {
      // Apply client-side filter to live events
      if (filterCategory && evt.category !== filterCategory) return;
      if (filterEventType && evt.event_type !== filterEventType) return;
      if (filterSeverity) {
        const order = { INFO: 0, WARNING: 1, CRITICAL: 2 };
        if (order[evt.severity] < order[filterSeverity]) return;
      }
      if (filterExamId && evt.exam_id !== Number(filterExamId)) return;
      if (filterHallId && evt.hall_id !== Number(filterHallId)) return;
    },
    [filterCategory, filterEventType, filterSeverity, filterExamId, filterHallId],
  );

  const { status: wsStatus, events: wsEvents, updateFilters } =
    useMonitoringSocket({ ...wsFilterArgs, onEvent: handleWsEvent });

  // Merge REST + WS events (dedup by event_id, newest first)
  const mergedEvents = useMemo(() => {
    const map = new Map<string, MonitoringEvent>();
    for (const e of wsEvents) map.set(e.event_id, e);
    for (const e of restEvents) {
      if (!map.has(e.event_id)) map.set(e.event_id, e);
    }
    const arr = Array.from(map.values());
    arr.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
    return arr;
  }, [restEvents, wsEvents]);

  // -------------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------------

  const loadStatus = useCallback(async () => {
    try {
      const data = await getMonitoringStatus();
      if (mountedRef.current) {
        setStatus(data);
        setStatusError("");
      }
    } catch (e: unknown) {
      if (mountedRef.current) {
        setStatusError(
          e instanceof Error ? e.message : "Failed to load status",
        );
      }
    }
  }, []);

  const loadEvents = useCallback(async () => {
    setEventsLoading(true);
    try {
      const data = await getMonitoringEvents({
        limit: filterLimit ? Number(filterLimit) : 50,
        category: filterCategory || undefined,
        event_type: filterEventType || undefined,
        min_severity: filterSeverity || undefined,
        exam_id: filterExamId ? Number(filterExamId) : undefined,
        hall_id: filterHallId ? Number(filterHallId) : undefined,
      });
      if (mountedRef.current) {
        setRestEvents(data.items);
        setEventsError("");
      }
    } catch (e: unknown) {
      if (mountedRef.current) {
        setEventsError(
          e instanceof Error ? e.message : "Failed to load events",
        );
      }
    } finally {
      if (mountedRef.current) setEventsLoading(false);
    }
  }, [
    filterLimit,
    filterCategory,
    filterEventType,
    filterSeverity,
    filterExamId,
    filterHallId,
  ]);

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true);
    try {
      const data = await getMonitoringAlerts({
        limit: alertLimit ? Number(alertLimit) : 50,
        severity: alertSeverity || undefined,
        event_type: alertEventType || undefined,
      });
      if (mountedRef.current) {
        setAlerts(data.items);
        setAlertsError("");
      }
    } catch (e: unknown) {
      if (mountedRef.current) {
        setAlertsError(
          e instanceof Error ? e.message : "Failed to load alerts",
        );
      }
    } finally {
      if (mountedRef.current) setAlertsLoading(false);
    }
  }, [alertLimit, alertSeverity, alertEventType]);

  // Initial load
  useEffect(() => {
    mountedRef.current = true;
    loadStatus();
    loadEvents();
    loadAlerts();
    return () => {
      mountedRef.current = false;
    };
  }, [loadStatus, loadEvents, loadAlerts]);

  // Refresh status periodically
  useEffect(() => {
    const id = setInterval(loadStatus, 15000);
    return () => clearInterval(id);
  }, [loadStatus]);

  // -------------------------------------------------------------------------
  // Filter apply
  // -------------------------------------------------------------------------

  const applyFilters = useCallback(() => {
    loadEvents();
    updateFilters({
      examId: filterExamId ? Number(filterExamId) : undefined,
      hallId: filterHallId ? Number(filterHallId) : undefined,
      category: filterCategory || undefined,
      eventType: filterEventType || undefined,
      minSeverity: filterSeverity || undefined,
    });
  }, [
    loadEvents,
    updateFilters,
    filterExamId,
    filterHallId,
    filterCategory,
    filterEventType,
    filterSeverity,
  ]);

  const applyAlertFilters = useCallback(() => {
    loadAlerts();
  }, [loadAlerts]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
      <div className="max-w-[1600px] mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <Link
              href="/dashboard"
              className="eg-mono-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] mb-3 inline-block"
            >
              &larr; DASHBOARD
            </Link>
            <h1 className="eg-display text-3xl tracking-tight">MONITORING</h1>
            <p className="eg-body text-[var(--text-secondary)] mt-1">
              Live examination entry activity and operational signals.
            </p>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span
              className={`w-2 h-2 rounded-full ${statusDot(wsStatus)}`}
            />
            <span className="eg-mono-sm text-[var(--text-secondary)]">
              {wsStatus === "CONNECTED"
                ? "CONNECTED"
                : wsStatus === "CONNECTING"
                  ? "CONNECTING"
                  : wsStatus === "RECONNECTING"
                    ? "RECONNECTING"
                    : wsStatus === "DISCONNECTED"
                      ? "DISCONNECTED"
                      : wsStatus === "ERROR"
                        ? "ERROR"
                        : "INITIALIZING"}
            </span>
          </div>
        </div>

        {/* Status Strip */}
        <div className="border border-white/[0.06] bg-[var(--bg-surface)] mb-6">
          {statusError ? (
            <div className="px-4 py-3">
              <span className="eg-mono-sm text-[var(--text-muted)]">
                STATUS UNAVAILABLE
              </span>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {statusError}
              </p>
            </div>
          ) : status ? (
            <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-white/[0.06]">
              <StatusCell
                label="CONNECTIONS"
                value={String(status.active_connections)}
                sub={` / ${status.max_connections}`}
              />
              <StatusCell
                label="EVENT BUFFER"
                value={String(status.buffered_events)}
                sub={` / ${status.event_buffer_capacity}`}
              />
              <StatusCell
                label="ALERT BUFFER"
                value={String(status.buffered_alerts)}
                sub={` / ${status.alert_buffer_capacity}`}
              />
              <StatusCell
                label="PUBLISHED"
                value={status.total_published.toLocaleString()}
              />
            </div>
          ) : (
            <div className="px-4 py-3">
              <span className="eg-mono-sm text-[var(--text-muted)]">
                Loading status...
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
          {/* Left: Events */}
          <div>
            {/* Event Filters */}
            <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-4 mb-4">
              <div className="eg-mono-sm text-[var(--text-muted)] mb-3">
                EVENT FILTERS
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <FilterSelect
                  label="CATEGORY"
                  value={filterCategory}
                  onChange={(v) => setFilterCategory(v as EventCategory | "")}
                  options={EVENT_CATEGORIES.map((c) => ({ value: c, label: c }))}
                  blank="ALL"
                />
                <FilterSelect
                  label="EVENT TYPE"
                  value={filterEventType}
                  onChange={(v) => setFilterEventType(v as EventType | "")}
                  options={EVENT_TYPES.map((t) => ({ value: t, label: t }))}
                  blank="ALL"
                />
                <FilterSelect
                  label="MIN SEVERITY"
                  value={filterSeverity}
                  onChange={(v) => setFilterSeverity(v as EventSeverity | "")}
                  options={SEVERITIES.map((s) => ({ value: s, label: s }))}
                  blank="ALL"
                />
                <FilterInput
                  label="EXAM ID"
                  value={filterExamId}
                  onChange={setFilterExamId}
                  placeholder="Any"
                />
                <FilterInput
                  label="HALL ID"
                  value={filterHallId}
                  onChange={setFilterHallId}
                  placeholder="Any"
                />
                <FilterInput
                  label="LIMIT"
                  value={filterLimit}
                  onChange={setFilterLimit}
                  placeholder="50"
                />
              </div>
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={applyFilters}
                  className="eg-btn eg-btn-primary"
                >
                  APPLY
                </button>
              </div>
            </div>

            {/* Event Stream */}
            <div className="border border-white/[0.06] bg-[var(--bg-surface)]">
              <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  EVENT STREAM
                </span>
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  {mergedEvents.length}
                </span>
              </div>
              {eventsError ? (
                <div className="px-4 py-8 text-center">
                  <span className="eg-mono-sm text-[var(--text-muted)]">
                    EVENTS UNAVAILABLE
                  </span>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    {eventsError}
                  </p>
                </div>
              ) : eventsLoading && mergedEvents.length === 0 ? (
                <div className="px-4 py-12 text-center">
                  <span className="eg-mono-sm text-[var(--text-muted)]">
                    Loading event stream...
                  </span>
                </div>
              ) : mergedEvents.length === 0 ? (
                <div className="px-4 py-12 text-center">
                  <h3 className="eg-mono text-[var(--text-secondary)] mb-1">
                    NO RETAINED EVENTS
                  </h3>
                  <p className="text-sm text-[var(--text-muted)]">
                    No monitoring events are currently available.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-white/[0.04]">
                  {mergedEvents.map((evt) => (
                    <EventRow
                      key={evt.event_id}
                      event={evt}
                      expanded={expandedId === evt.event_id}
                      onToggle={() =>
                        setExpandedId(
                          expandedId === evt.event_id ? null : evt.event_id,
                        )
                      }
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right: Alerts */}
          <div>
            {/* Alert Filters */}
            <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-4 mb-4">
              <div className="eg-mono-sm text-[var(--text-muted)] mb-3">
                ALERT FILTERS
              </div>
              <div className="grid grid-cols-2 gap-3">
                <FilterSelect
                  label="SEVERITY"
                  value={alertSeverity}
                  onChange={(v) => setAlertSeverity(v as EventSeverity | "")}
                  options={SEVERITIES.map((s) => ({ value: s, label: s }))}
                  blank="ALL"
                />
                <FilterSelect
                  label="EVENT TYPE"
                  value={alertEventType}
                  onChange={(v) => setAlertEventType(v as EventType | "")}
                  options={EVENT_TYPES.map((t) => ({ value: t, label: t }))}
                  blank="ALL"
                />
              </div>
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={applyAlertFilters}
                  className="eg-btn eg-btn-primary"
                >
                  APPLY
                </button>
              </div>
            </div>

            {/* Alert Panel */}
            <div className="border border-white/[0.06] bg-[var(--bg-surface)]">
              <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  ALERTS
                </span>
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  {alerts.length}
                </span>
              </div>
              {alertsError ? (
                <div className="px-4 py-8 text-center">
                  <span className="eg-mono-sm text-[var(--text-muted)]">
                    ALERTS UNAVAILABLE
                  </span>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    {alertsError}
                  </p>
                </div>
              ) : alertsLoading && alerts.length === 0 ? (
                <div className="px-4 py-12 text-center">
                  <span className="eg-mono-sm text-[var(--text-muted)]">
                    Loading alerts...
                  </span>
                </div>
              ) : alerts.length === 0 ? (
                <div className="px-4 py-12 text-center">
                  <h3 className="eg-mono text-[var(--text-secondary)] mb-1">
                    NO RETAINED ALERTS
                  </h3>
                  <p className="text-sm text-[var(--text-muted)]">
                    No operational alerts are currently available.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-white/[0.04]">
                  {alerts.map((a) => (
                    <AlertRow key={a.alert_id} alert={a} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusCell({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="px-4 py-3">
      <div className="eg-mono-sm text-[var(--text-muted)] mb-1">{label}</div>
      <div className="eg-mono text-xl text-[var(--text-primary)]">
        {value}
        {sub && (
          <span className="text-sm text-[var(--text-muted)]">{sub}</span>
        )}
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  blank,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  blank: string;
}) {
  return (
    <div>
      <label className="eg-mono-sm text-[var(--text-muted)] block mb-1">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-[var(--bg-raised)] border border-white/[0.08] text-[var(--text-secondary)] eg-mono-sm px-2 py-1.5 focus:outline-none focus:border-white/20"
      >
        <option value="">{blank}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function FilterInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <label className="eg-mono-sm text-[var(--text-muted)] block mb-1">
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-[var(--bg-raised)] border border-white/[0.08] text-[var(--text-secondary)] eg-mono-sm px-2 py-1.5 placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/20"
      />
    </div>
  );
}
