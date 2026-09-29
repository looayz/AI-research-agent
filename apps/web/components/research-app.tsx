"use client";

import { Menu, WifiOff } from "lucide-react";
import { useCallback, useEffect, useReducer, useState } from "react";

import { api } from "@/lib/api";
import { useHealth, useRoute } from "@/lib/hooks";
import type { Depth, Domain, ResearchSummary } from "@/lib/types";
import { isTerminal } from "@/lib/types";

import { HistoryView } from "./history-view";
import { HomeView } from "./home-view";
import { Logo } from "./logo";
import { MemoryView } from "./memory-view";
import { ResearchView } from "./research-view";
import { Sidebar } from "./sidebar";
import { ThemeToggle } from "./theme";
import { ToastProvider, useToast } from "./ui";

function Shell() {
  const [route, navigate] = useRoute();
  const { health, offline } = useHealth();
  const toast = useToast();
  const [version, bump] = useReducer((n: number) => n + 1, 0);
  const [recent, setRecent] = useState<ResearchSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .listResearch({ limit: 8 })
      .then((data) => {
        if (!active) return;
        setRecent(data.items);
        setTotal(data.total);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [version, offline]);

  // Keep the sidebar statuses fresh while something runs in the background.
  const anyRunning = recent.some((item) => !isTerminal(item.status));
  useEffect(() => {
    if (!anyRunning) return;
    const timer = window.setInterval(bump, 4000);
    return () => window.clearInterval(timer);
  }, [anyRunning]);

  const onChanged = useCallback(() => bump(), []);

  const startResearch = useCallback(
    async (payload: { question: string; depth: Depth; domain: Domain }) => {
      try {
        const created = await api.createResearch(payload);
        bump();
        navigate({ view: "research", id: created.id });
      } catch (e) {
        toast((e as Error).message, "danger");
      }
    },
    [navigate, toast],
  );

  const title =
    route.view === "history" ? "Investigations" : route.view === "memory" ? "Semantic memory" : route.view === "research" ? "Investigation" : "New research";
  useEffect(() => {
    document.title = `${title} · AI Research Agent`;
  }, [title]);

  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <Sidebar
        route={route}
        navigate={navigate}
        recent={recent}
        total={total}
        health={health}
        offline={offline}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-bg/85 px-4 backdrop-blur lg:hidden">
          <button type="button" onClick={() => setDrawerOpen(true)} className="rounded-md p-1.5 text-fg-muted hover:text-fg" aria-label="Open menu">
            <Menu className="size-5" />
          </button>
          <Logo className="size-7" />
          <span className="flex-1 truncate text-sm font-semibold">{title}</span>
          <ThemeToggle className="text-fg-muted hover:bg-muted hover:text-fg" />
        </header>
        {offline && (
          <div role="alert" className="no-print flex items-center justify-center gap-2 border-b border-danger/30 bg-danger/10 px-4 py-2 text-xs text-danger">
            <WifiOff className="size-3.5" aria-hidden />
            The API is unreachable. Start the backend (port 8000) or check API_INTERNAL_URL.
          </div>
        )}
        <main id="main" className="flex-1">
          {route.view === "home" && (
            <HomeView health={health} recent={recent} onSubmit={startResearch} onOpen={(id) => navigate({ view: "research", id })} />
          )}
          {route.view === "research" && <ResearchView key={route.id} id={route.id} navigate={navigate} onChanged={onChanged} />}
          {route.view === "history" && <HistoryView navigate={navigate} version={version} onChanged={onChanged} />}
          {route.view === "memory" && <MemoryView navigate={navigate} />}
        </main>
      </div>
    </div>
  );
}

export function ResearchApp() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}
