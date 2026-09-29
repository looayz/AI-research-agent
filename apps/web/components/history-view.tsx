"use client";

import { History, RotateCcw, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { cn, formatDate, formatDuration, plural, timeAgo } from "@/lib/format";
import type { Route } from "@/lib/hooks";
import { useDebounced } from "@/lib/hooks";
import { DEPTHS, DOMAINS, STATUS_META, TONE_BADGE } from "@/lib/meta";
import type { ResearchStatus, ResearchSummary } from "@/lib/types";
import { isTerminal } from "@/lib/types";

import { Button, Card, ConfirmDialog, EmptyState, Spinner, useToast } from "./ui";

const PAGE_SIZE = 20;
const STATUS_FILTERS: { value: ResearchStatus | ""; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

export function HistoryView({
  navigate,
  version,
  onChanged,
}: {
  navigate: (route: Route) => void;
  version: number;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ResearchStatus | "">("");
  const [items, setItems] = useState<ResearchSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [toDelete, setToDelete] = useState<ResearchSummary | null>(null);
  const debouncedQuery = useDebounced(query, 250);
  const requestKey = `${debouncedQuery}|${status}|${version}`;
  const loading = loadedKey !== requestKey;

  useEffect(() => {
    let active = true;
    api
      .listResearch({ limit: PAGE_SIZE, q: debouncedQuery, status })
      .then((data) => {
        if (!active) return;
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((e) => active && toast((e as Error).message, "danger"))
      .finally(() => active && setLoadedKey(requestKey));
    return () => {
      active = false;
    };
  }, [debouncedQuery, status, requestKey, toast]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await api.listResearch({ limit: PAGE_SIZE, offset: items.length, q: debouncedQuery, status });
      setItems((current) => [...current, ...data.items]);
      setTotal(data.total);
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setLoadingMore(false);
    }
  };

  const rerun = async (item: ResearchSummary) => {
    try {
      const created = await api.rerun(item.id);
      onChanged();
      navigate({ view: "research", id: created.id });
    } catch (e) {
      toast((e as Error).message, "danger");
    }
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-4 pb-20 pt-8 sm:px-6">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Investigations</h1>
          <p className="mt-1 text-sm text-fg-muted">
            {plural(total, "investigation")} with their plans, sources, verified claims and reports.
          </p>
        </div>
        <div className="flex gap-2">
          <label className="relative block">
            <span className="sr-only">Search investigations</span>
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search questions…"
              className="h-9 w-full rounded-lg border border-line bg-surface pl-8 pr-3 text-sm placeholder:text-fg-subtle focus:border-line-strong focus:outline-none sm:w-64"
            />
          </label>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(event) => setStatus(event.target.value as ResearchStatus | "")}
            className="h-9 rounded-lg border border-line bg-surface px-2 text-sm"
          >
            {STATUS_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && items.length === 0 ? (
        <div className="flex items-center gap-3 py-10 text-sm text-fg-muted">
          <Spinner /> Loading…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={History}
          title={query || status ? "No matching investigation" : "No investigations yet"}
          action={!query && !status ? <Button variant="primary" onClick={() => navigate({ view: "home" })}>Start your first research</Button> : undefined}
        >
          {query || status ? "Try another search or status filter." : "Every research you run is archived here."}
        </EmptyState>
      ) : (
        <ul className={cn("space-y-2.5 transition-opacity", loading && "opacity-60")}>
          {items.map((item) => {
            const meta = STATUS_META[item.status];
            const running = !isTerminal(item.status);
            return (
              <li key={item.id}>
                <Card className="group flex flex-col gap-3 p-4 transition-colors hover:border-line-strong sm:flex-row sm:items-center">
                  <button type="button" onClick={() => navigate({ view: "research", id: item.id })} className="min-w-0 flex-1 text-left">
                    <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
                      <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium", TONE_BADGE[meta.tone])}>
                        {running && <Spinner className="size-3" />}
                        {meta.label}
                      </span>
                      <span>{DOMAINS[item.domain].label}</span>
                      <span>· {DEPTHS[item.depth].label}</span>
                      <span title={formatDate(item.created_at)}>· {timeAgo(item.created_at)}</span>
                    </div>
                    <p className="font-medium leading-snug group-hover:underline">{item.question}</p>
                    {item.status === "failed" ? (
                      <p className="mt-1 line-clamp-1 text-sm text-danger">{item.error_message}</p>
                    ) : (
                      item.executive_summary && <p className="mt-1 line-clamp-2 text-sm text-fg-muted">{item.executive_summary}</p>
                    )}
                    <p className="mt-2 font-mono text-[11px] text-fg-subtle">
                      {plural(item.source_count, "source")} · {plural(item.claim_count, "claim")} ·{" "}
                      {plural(item.contradiction_count, "contradiction")}
                      {item.follow_up_count > 0 && ` · ${plural(item.follow_up_count, "follow-up query", "follow-up queries")}`} ·{" "}
                      {formatDuration(item.runtime_seconds)}
                    </p>
                  </button>
                  <div className="flex shrink-0 gap-1.5 sm:flex-col lg:flex-row">
                    <Button size="sm" icon={RotateCcw} onClick={() => rerun(item)} disabled={running}>
                      Rerun
                    </Button>
                    <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setToDelete(item)} aria-label={`Delete “${item.question}”`} />
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      {items.length < total && (
        <div className="mt-6 flex justify-center">
          <Button onClick={loadMore} loading={loadingMore}>
            Load more ({total - items.length} remaining)
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this investigation?"
        description={toDelete ? <span className="line-clamp-3">“{toDelete.question}” and its sources, claims and report will be removed.</span> : null}
        confirmLabel="Delete"
        onClose={() => setToDelete(null)}
        onConfirm={async () => {
          if (!toDelete) return;
          try {
            await api.remove(toDelete.id);
            setItems((current) => current.filter((i) => i.id !== toDelete.id));
            setTotal((t) => t - 1);
            toast("Investigation deleted");
            onChanged();
          } catch (e) {
            toast((e as Error).message, "danger");
          }
        }}
      />
    </div>
  );
}
