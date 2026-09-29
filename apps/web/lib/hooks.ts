"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { api, ApiError } from "./api";
import { isTerminal, type Health, type ResearchDetail, type ResearchEvent } from "./types";

/* ------------------------------------------------------------ routing */

export type Route = { view: "home" } | { view: "research"; id: string } | { view: "history" } | { view: "memory" };

const ROUTE_EVENT = "app:navigate";

function readRoute(): Route {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("r");
  if (id) return { view: "research", id };
  const view = params.get("view");
  if (view === "history" || view === "memory") return { view };
  return { view: "home" };
}

function routeToSearch(route: Route): string {
  if (route.view === "research") return `?r=${encodeURIComponent(route.id)}`;
  if (route.view === "history" || route.view === "memory") return `?view=${route.view}`;
  return window.location.pathname;
}

let cachedKey = "";
let cachedRoute: Route = { view: "home" };

function subscribe(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener(ROUTE_EVENT, callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener(ROUTE_EVENT, callback);
  };
}

function getSnapshot(): Route {
  const key = window.location.search;
  if (key !== cachedKey) {
    cachedKey = key;
    cachedRoute = readRoute();
  }
  return cachedRoute;
}

const serverRoute: Route = { view: "home" };

export function useRoute(): [Route, (route: Route, options?: { replace?: boolean }) => void] {
  const route = useSyncExternalStore(subscribe, getSnapshot, () => serverRoute);
  const navigate = useCallback((next: Route, options?: { replace?: boolean }) => {
    const url = routeToSearch(next);
    if (options?.replace) window.history.replaceState(null, "", url);
    else window.history.pushState(null, "", url);
    window.dispatchEvent(new Event(ROUTE_EVENT));
    window.scrollTo?.({ top: 0 });
  }, []);
  return [route, navigate];
}

/* ------------------------------------------------------------- health */

export function useHealth(intervalMs = 30_000) {
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let active = true;
    const check = () =>
      api
        .health()
        .then((data) => active && (setHealth(data), setOffline(false)))
        .catch(() => active && setOffline(true));
    check();
    const timer = window.setInterval(check, intervalMs);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [intervalMs]);

  return { health, offline };
}

/* ----------------------------------------------------------- research */

// Events after which the stored results changed enough to refetch them.
const REFRESH_ON = new Set([
  "planner.completed",
  "memory.recalled",
  "search.completed",
  "verifier.completed",
  "gap_analyzer.completed",
  "synthesizer.completed",
  "research.completed",
  "research.failed",
  "research.cancelled",
]);

function mergeEvents(current: ResearchEvent[], incoming: ResearchEvent[]): ResearchEvent[] {
  if (!incoming.length) return current;
  const bySeq = new Map(current.map((e) => [e.seq || e.id, e]));
  for (const event of incoming) bySeq.set(event.seq || event.id, event);
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq || a.created_at.localeCompare(b.created_at));
}

export function useResearch(id: string | null, onSettled?: () => void) {
  const [detail, setDetail] = useState<ResearchDetail | null>(null);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);
  const [live, setLive] = useState(false);
  const lastSeq = useRef(0);
  const refreshTimer = useRef<number | null>(null);
  const onSettledRef = useRef(onSettled);
  useEffect(() => {
    onSettledRef.current = onSettled;
  }, [onSettled]);

  const load = useCallback((): Promise<ResearchDetail | null> => {
    if (!id) return Promise.resolve(null);
    return api.getResearch(id).then(
      (data) => {
        setDetail(data);
        setEvents((prev) => mergeEvents(prev, data.events));
        lastSeq.current = Math.max(lastSeq.current, ...data.events.map((e) => e.seq));
        setError(null);
        return data;
      },
      (e: unknown) => {
        setError({ message: (e as Error).message, status: e instanceof ApiError ? e.status : 0 });
        return null;
      },
    );
  }, [id]);

  const scheduleRefresh = useCallback(
    (delay = 250) => {
      if (refreshTimer.current !== null) return;
      refreshTimer.current = window.setTimeout(() => {
        refreshTimer.current = null;
        void load();
      }, delay);
    },
    [load],
  );

  // Initial load. Callers key the component by research id, so state starts fresh.
  useEffect(() => {
    if (id) void load();
  }, [id, load]);

  const running = !!detail && !isTerminal(detail.status);

  // Live updates while the research runs.
  useEffect(() => {
    if (!id || !running) return;
    let pollTimer: number | null = null;
    const source = new EventSource(api.eventsUrl(id, lastSeq.current));
    source.onopen = () => setLive(true);

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as ResearchEvent;
      lastSeq.current = Math.max(lastSeq.current, event.seq);
      setEvents((prev) => mergeEvents(prev, [event]));
      if (event.status) setDetail((d) => (d && d.status !== event.status ? { ...d, status: event.status! } : d));
      if (REFRESH_ON.has(event.event_type)) scheduleRefresh(event.event_type.startsWith("research.") ? 0 : 250);
    };
    source.addEventListener("end", () => {
      source.close();
      setLive(false);
      void load().then(() => onSettledRef.current?.());
    });
    source.onerror = () => {
      // The browser reconnects by itself (resuming with Last-Event-ID); if it
      // gave up, fall back to polling.
      if (source.readyState === EventSource.CLOSED && pollTimer === null) {
        setLive(false);
        pollTimer = window.setInterval(async () => {
          const data = await load();
          if (data && isTerminal(data.status)) {
            window.clearInterval(pollTimer!);
            onSettledRef.current?.();
          }
        }, 2000);
      }
    };
    return () => {
      source.close();
      if (pollTimer !== null) window.clearInterval(pollTimer);
      setLive(false);
    };
  }, [id, running, load, scheduleRefresh]);

  useEffect(
    () => () => {
      if (refreshTimer.current !== null) window.clearTimeout(refreshTimer.current);
    },
    [],
  );

  return { detail, setDetail, events, error, live, reload: load };
}

/* -------------------------------------------------------------- misc */

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useHotkey(key: string, handler: (event: KeyboardEvent) => void, enabled = true) {
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);
  useEffect(() => {
    if (!enabled) return;
    const listener = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
      if (event.key === key && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) handlerRef.current(event);
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [key, enabled]);
}
