"use client";

import { Brain, CircleAlert, Database, History, Plus, X } from "lucide-react";

import { cn } from "@/lib/format";
import type { Route } from "@/lib/hooks";
import type { Health, ResearchSummary } from "@/lib/types";
import { isTerminal } from "@/lib/types";

import { ThemeToggle } from "./theme";
import { Logo } from "./logo";

function StatusDot({ status }: { status: ResearchSummary["status"] }) {
  if (!isTerminal(status)) {
    return (
      <span className="relative flex size-2" aria-label="Running">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-info opacity-60" />
        <span className="relative inline-flex size-2 rounded-full bg-info" />
      </span>
    );
  }
  const color = status === "completed" ? "bg-success" : status === "failed" ? "bg-danger" : "bg-sidebar-muted";
  return <span className={cn("size-2 rounded-full", color)} aria-label={status} />;
}

function NavButton({
  active,
  icon: Icon,
  label,
  count,
  onClick,
}: {
  active: boolean;
  icon: typeof History;
  label: string;
  count?: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors",
        active ? "bg-sidebar-hover text-sidebar-fg" : "text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg",
      )}
    >
      <Icon className="size-4" aria-hidden />
      <span className="flex-1 text-left">{label}</span>
      {count !== undefined && <span className="font-mono text-[11px] text-sidebar-muted">{count}</span>}
    </button>
  );
}

function BackendStatus({ health, offline }: { health: Health | null; offline: boolean }) {
  if (offline) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/10 px-2.5 py-2 text-xs text-danger">
        <CircleAlert className="size-3.5 shrink-0" aria-hidden />
        API unreachable
      </div>
    );
  }
  if (!health) return <div className="h-[74px] animate-pulse rounded-lg bg-sidebar-hover" />;
  const rows = [
    ["LLM", health.llm.provider === "mock" ? "demo" : `${health.llm.provider} · ${health.llm.model}`],
    ["Search", health.search.providers.join(" + ").replace("mock", "demo")],
    ["Storage", health.database.backend],
  ];
  return (
    <div className="space-y-1.5 rounded-lg border border-sidebar-line px-2.5 py-2">
      {health.demo_mode && (
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-warning">
          <span className="size-1.5 rounded-full bg-warning" aria-hidden /> Demo mode
        </div>
      )}
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-3 text-[11px]">
          <span className="text-sidebar-muted">{label}</span>
          <span className="truncate font-mono text-sidebar-fg" title={value}>
            {value}
          </span>
        </div>
      ))}
      {(!health.llm.configured || !health.search.configured) && (
        <p className="pt-1 text-[11px] leading-snug text-warning">A provider is missing its API key or URL.</p>
      )}
    </div>
  );
}

export function Sidebar({
  route,
  navigate,
  recent,
  total,
  health,
  offline,
  open,
  onClose,
}: {
  route: Route;
  navigate: (route: Route) => void;
  recent: ResearchSummary[];
  total: number;
  health: Health | null;
  offline: boolean;
  open: boolean;
  onClose: () => void;
}) {
  const go = (next: Route) => {
    navigate(next);
    onClose();
  };
  return (
    <>
      <div
        className={cn("fixed inset-0 z-30 bg-black/50 transition-opacity lg:hidden", open ? "opacity-100" : "pointer-events-none opacity-0")}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cn(
          "no-print fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col border-r border-sidebar-line bg-sidebar text-sidebar-fg transition-transform duration-200 lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Main navigation"
      >
        <div className="flex items-center justify-between px-4 pb-3 pt-4">
          <button type="button" onClick={() => go({ view: "home" })} className="flex items-center gap-2.5" aria-label="Home">
            <Logo className="size-8" />
            <div className="text-left">
              <p className="text-sm font-semibold leading-tight">Research Agent</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-sidebar-muted">
                multi-agent · v{health?.version ?? "0.3"}
              </p>
            </div>
          </button>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-sidebar-muted hover:text-sidebar-fg lg:hidden" aria-label="Close menu">
            <X className="size-5" />
          </button>
        </div>

        <div className="px-3">
          <button
            type="button"
            onClick={() => go({ view: "home" })}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-sidebar-fg px-3 py-2 text-sm font-semibold text-sidebar shadow-sm transition-opacity hover:opacity-90"
          >
            <Plus className="size-4" aria-hidden /> New research
          </button>
        </div>

        <nav className="mt-4 space-y-0.5 px-3">
          <NavButton active={route.view === "history"} icon={History} label="Investigations" count={total} onClick={() => go({ view: "history" })} />
          <NavButton active={route.view === "memory"} icon={Database} label="Semantic memory" onClick={() => go({ view: "memory" })} />
        </nav>

        <div className="mt-6 flex min-h-0 flex-1 flex-col px-3">
          <p className="px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted">Recent</p>
          <div className="-mx-1 flex-1 space-y-0.5 overflow-y-auto px-1">
            {recent.length === 0 && <p className="px-2.5 py-1 text-xs text-sidebar-muted">No investigations yet.</p>}
            {recent.map((item) => {
              const active = route.view === "research" && route.id === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => go({ view: "research", id: item.id })}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] transition-colors",
                    active ? "bg-sidebar-hover text-sidebar-fg" : "text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg",
                  )}
                  title={item.question}
                >
                  <StatusDot status={item.status} />
                  <span className="truncate">{item.report_title || item.question}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2 border-t border-sidebar-line p-3">
          <BackendStatus health={health} offline={offline} />
          <div className="flex items-center justify-between px-1">
            <a
              href="/api/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-[11px] text-sidebar-muted hover:text-sidebar-fg"
            >
              <Brain className="size-3.5" aria-hidden /> API docs
            </a>
            <ThemeToggle className="text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-fg" />
          </div>
        </div>
      </aside>
    </>
  );
}
