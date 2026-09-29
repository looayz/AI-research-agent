"use client";

import {
  Activity,
  ArrowLeft,
  BookOpen,
  Check,
  Compass,
  Download,
  FileJson,
  FileText,
  Link2,
  Printer,
  RotateCcw,
  Scale,
  ShieldCheck,
  Square,
  Trash2,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { cn, formatDate, formatDuration, formatNumber, timeAgo } from "@/lib/format";
import type { Route } from "@/lib/hooks";
import { useResearch } from "@/lib/hooks";
import { DEPTHS, DOMAINS, STATUS_META, TONE_BADGE } from "@/lib/meta";
import { SourceIndex, type SourceRef } from "@/lib/sources";
import type { Source } from "@/lib/types";
import { isTerminal } from "@/lib/types";

import { Pipeline } from "./pipeline";
import { ActivityTab } from "./tabs/activity-tab";
import { ClaimsTab } from "./tabs/claims-tab";
import { ContradictionsTab } from "./tabs/contradictions-tab";
import { PlanTab } from "./tabs/plan-tab";
import { ReportTab } from "./tabs/report-tab";
import { SourcesTab } from "./tabs/sources-tab";
import { Button, ConfirmDialog, EmptyState, Spinner, useToast } from "./ui";

type TabKey = "report" | "claims" | "contradictions" | "sources" | "plan" | "activity";

function ExportMenu({ id, onPrint }: { id: string; onPrint: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const item = "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm text-fg hover:bg-muted";
  return (
    <div ref={ref} className="relative">
      <Button icon={Download} onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}>
        Export
      </Button>
      {open && (
        <div role="menu" className="absolute right-0 z-20 mt-1.5 w-52 animate-fade-in rounded-lg border border-line bg-surface p-1 shadow-lg">
          <a role="menuitem" href={api.exportUrl(id, "md")} download className={item} onClick={() => setOpen(false)}>
            <FileText className="size-4 text-fg-muted" aria-hidden /> Markdown report
          </a>
          <a role="menuitem" href={api.exportUrl(id, "json")} download className={item} onClick={() => setOpen(false)}>
            <FileJson className="size-4 text-fg-muted" aria-hidden /> Full data (JSON)
          </a>
          <button
            role="menuitem"
            type="button"
            className={item}
            onClick={() => {
              setOpen(false);
              onPrint();
            }}
          >
            <Printer className="size-4 text-fg-muted" aria-hidden /> Print / save as PDF
          </button>
        </div>
      )}
    </div>
  );
}

export function ResearchView({
  id,
  navigate,
  onChanged,
}: {
  id: string;
  navigate: (route: Route) => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const { detail, setDetail, events, error, live, reload } = useResearch(id, onChanged);
  const [tab, setTab] = useState<TabKey | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState<"cancel" | "rerun" | null>(null);
  const index = useMemo(() => new SourceIndex(detail), [detail]);

  const openSource = useCallback((ref: SourceRef | string) => {
    const sourceId = typeof ref === "string" ? ref : ref.source?.id;
    if (!sourceId) {
      if (typeof ref !== "string") window.open(ref.url, "_blank", "noopener,noreferrer");
      return;
    }
    setTab("sources");
    setHighlight(null);
    window.requestAnimationFrame(() => setHighlight(sourceId));
  }, []);

  if (!detail) {
    if (error) {
      return (
        <div className="mx-auto max-w-2xl px-4 py-16">
          <EmptyState
            icon={TriangleAlert}
            title={error.status === 404 ? "This investigation does not exist (anymore)" : "Could not load this investigation"}
            action={<Button onClick={() => navigate({ view: "home" })}>Start a new research</Button>}
          >
            {error.status === 404 ? "It may have been deleted." : error.message}
          </EmptyState>
        </div>
      );
    }
    return (
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-16 text-sm text-fg-muted sm:px-6">
        <Spinner /> Loading investigation…
      </div>
    );
  }

  const running = !isTerminal(detail.status);
  const status = STATUS_META[detail.status];
  const activeTab: TabKey = tab ?? (detail.report ? "report" : "activity");
  const DomainIcon = DOMAINS[detail.domain].icon;

  const tabs: { key: TabKey; label: string; icon: LucideIcon; count?: number }[] = [
    { key: "report", label: "Report", icon: FileText },
    { key: "claims", label: "Claims", icon: ShieldCheck, count: detail.claims.length },
    { key: "contradictions", label: "Contradictions", icon: Scale, count: detail.contradictions.length },
    { key: "sources", label: "Sources", icon: BookOpen, count: detail.sources.length },
    { key: "plan", label: "Plan", icon: Compass },
    { key: "activity", label: "Activity", icon: Activity, count: events.length },
  ];

  const cancel = async () => {
    setBusy("cancel");
    try {
      const updated = await api.cancel(detail.id);
      setDetail((d) => (d ? { ...d, status: updated.status } : d));
      toast("Research cancelled", "warning");
      onChanged();
      void reload();
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBusy(null);
    }
  };

  const rerun = async () => {
    setBusy("rerun");
    try {
      const created = await api.rerun(detail.id);
      onChanged();
      navigate({ view: "research", id: created.id });
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setBusy(null);
    }
  };

  const resynthesize = async () => {
    try {
      const updated = await api.resynthesize(detail.id);
      setDetail((d) => (d ? { ...d, status: updated.status } : d));
      toast("Regenerating the report from the selected sources…", "info");
      onChanged();
    } catch (e) {
      toast((e as Error).message, "danger");
    }
  };

  const toggleSource = async (source: Source) => {
    try {
      const updated = await api.setSourceExcluded(detail.id, source.id, !source.is_excluded);
      setDetail((d) => (d ? { ...d, sources: d.sources.map((s) => (s.id === updated.id ? { ...s, is_excluded: updated.is_excluded } : s)) } : d));
    } catch (e) {
      toast((e as Error).message, "danger");
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast("Copy failed: clipboard not available", "danger");
    }
  };

  const print = () => {
    setTab("report");
    window.setTimeout(() => window.print(), 150);
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-4 pb-20 pt-6 sm:px-6 sm:pt-8">
      <button
        type="button"
        onClick={() => navigate({ view: "history" })}
        className="no-print mb-4 inline-flex items-center gap-1.5 text-xs text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="size-3.5" aria-hidden /> Investigations
      </button>

      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-balance text-xl font-semibold leading-snug tracking-tight sm:text-2xl">{detail.question}</h1>
          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-fg-muted">
            <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-medium", TONE_BADGE[status.tone])}>
              {running ? <Spinner className="size-3" /> : <span className="size-1.5 rounded-full bg-current" aria-hidden />}
              {status.label}
            </span>
            <span className="inline-flex items-center gap-1">
              <DomainIcon className="size-3.5" aria-hidden /> {DOMAINS[detail.domain].label}
            </span>
            <span>{DEPTHS[detail.depth].label}</span>
            <span title={formatDate(detail.created_at)}>{timeAgo(detail.created_at)}</span>
            <span className="font-mono">{formatDuration(detail.runtime_seconds)}</span>
            <span className="font-mono">{formatNumber(detail.tokens_used)} tokens</span>
            <span className="font-mono">{detail.llm_calls} LLM calls</span>
          </div>
        </div>
        <div className="no-print flex shrink-0 flex-wrap gap-2">
          <Button variant="ghost" icon={copied ? Check : Link2} onClick={copyLink} title="Copy link" aria-label="Copy link" />
          {running ? (
            <Button variant="danger" icon={Square} onClick={cancel} loading={busy === "cancel"}>
              Cancel
            </Button>
          ) : (
            <>
              <Button icon={RotateCcw} onClick={rerun} loading={busy === "rerun"}>
                Rerun
              </Button>
              {detail.report && <ExportMenu id={detail.id} onPrint={print} />}
              <Button variant="ghost" icon={Trash2} onClick={() => setConfirmDelete(true)} aria-label="Delete" title="Delete" />
            </>
          )}
        </div>
      </header>

      {detail.status === "failed" && (
        <div role="alert" className="mt-5 flex gap-3 rounded-xl border border-danger/30 bg-danger/[0.06] p-4 text-sm">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
          <div>
            <p className="font-medium text-danger">The research failed</p>
            <p className="mt-0.5 break-words text-fg-muted">{detail.error_message || "Unknown error"}</p>
          </div>
        </div>
      )}

      <div className="no-print mt-5">
        <Pipeline events={events} depth={detail.depth} running={running} />
      </div>

      <div className="no-print mt-6 overflow-x-auto border-b border-line">
        <div role="tablist" aria-label="Research results" className="flex min-w-max gap-1">
          {tabs.map(({ key, label, icon: Icon, count }) => {
            const selected = activeTab === key;
            return (
              <button
                key={key}
                type="button"
                role="tab"
                id={`tab-${key}`}
                aria-selected={selected}
                aria-controls={`panel-${key}`}
                onClick={() => setTab(key)}
                className={cn(
                  "-mb-px flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  selected ? "border-fg text-fg" : "border-transparent text-fg-muted hover:text-fg",
                )}
              >
                <Icon className="size-4" aria-hidden />
                {label}
                {count !== undefined && count > 0 && (
                  <span className="rounded-full bg-muted px-1.5 font-mono text-[10px] text-fg-muted">{count}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div id={`panel-${activeTab}`} role="tabpanel" aria-labelledby={`tab-${activeTab}`} className="mt-5 animate-fade-in" key={activeTab}>
        {activeTab === "report" && <ReportTab detail={detail} events={events} onResynthesize={resynthesize} onOpenSource={openSource} />}
        {activeTab === "claims" && <ClaimsTab detail={detail} index={index} onOpenSource={openSource} />}
        {activeTab === "contradictions" && <ContradictionsTab detail={detail} index={index} onOpenSource={openSource} />}
        {activeTab === "sources" && (
          <SourcesTab detail={detail} index={index} highlightId={highlight} onToggleExcluded={toggleSource} onResynthesize={resynthesize} />
        )}
        {activeTab === "plan" && <PlanTab detail={detail} />}
        {activeTab === "activity" && <ActivityTab events={events} live={live} />}
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this investigation?"
        description="The report, claims and collected sources are removed permanently. Sources stay in semantic memory only through other investigations."
        confirmLabel="Delete"
        onClose={() => setConfirmDelete(false)}
        onConfirm={async () => {
          try {
            await api.remove(detail.id);
            toast("Investigation deleted");
            onChanged();
            navigate({ view: "history" });
          } catch (e) {
            toast((e as Error).message, "danger");
          }
        }}
      />
    </div>
  );
}
