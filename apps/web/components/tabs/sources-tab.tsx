"use client";

import { Ban, BookOpen, ChevronDown, ExternalLink, RefreshCw, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { cn, humanize, percent, safeHref } from "@/lib/format";
import type { SourceIndex } from "@/lib/sources";
import type { ResearchDetail, Source } from "@/lib/types";
import { isTerminal } from "@/lib/types";

import { Badge, Button, Card, EmptyState, Meter, Spinner, useToast } from "../ui";

type Filter = "all" | "cited" | "excluded" | "memory" | "follow_up" | "snippet";
type Sort = "relevance" | "report";

const FILTERS: { key: Filter; label: string; test: (s: Source, numbered: boolean) => boolean }[] = [
  { key: "all", label: "All", test: () => true },
  { key: "cited", label: "In report", test: (_, numbered) => numbered },
  { key: "excluded", label: "Excluded", test: (s) => s.is_excluded },
  { key: "memory", label: "From memory", test: (s) => s.origin === "memory" },
  { key: "follow_up", label: "Follow-up", test: (s) => s.origin === "follow_up" },
  { key: "snippet", label: "Snippet only", test: (s) => s.fetch_status === "snippet" },
];

const FACTORS: [string, string][] = [
  ["authority", "Source authority"],
  ["query_match", "Match with the question"],
  ["search_rank", "Search ranking"],
  ["content_depth", "Content depth"],
  ["freshness", "Freshness"],
];

function SourceCard({
  source,
  number,
  researchId,
  highlighted,
  locked,
  onToggle,
}: {
  source: Source;
  number?: number;
  researchId: string;
  highlighted: boolean;
  locked: boolean;
  onToggle: (source: Source) => Promise<void>;
}) {
  const ref = useRef<HTMLLIElement>(null);
  const [fullText, setFullText] = useState<string | null>(null);
  const [loadingText, setLoadingText] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (highlighted) ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlighted]);

  const loadFullText = async () => {
    if (fullText !== null) return setFullText(null);
    setLoadingText(true);
    try {
      setFullText((await api.getSource(researchId, source.id)).content);
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setLoadingText(false);
    }
  };

  const href = safeHref(source.url);
  const factors = source.evaluation_factors;
  return (
    <li ref={ref} className={cn("rounded-xl", highlighted && "animate-flash")}>
      <Card className={cn("p-4 sm:p-5", source.is_excluded && "border-dashed bg-surface-2")}>
        <div className="flex items-start gap-3">
          <span
            className={cn(
              "mt-0.5 grid h-6 min-w-6 shrink-0 place-items-center rounded-md px-1 font-mono text-[11px] font-semibold",
              number !== undefined ? "bg-fg text-bg" : "bg-muted text-fg-subtle",
            )}
            title={number !== undefined ? `Cited as [${number}] in the report` : "Not part of the report"}
          >
            {number ?? "–"}
          </span>
          <div className="min-w-0 flex-1">
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className={cn("font-medium leading-snug hover:underline", source.is_excluded && "text-fg-muted line-through")}
            >
              {source.title}
              <ExternalLink className="ml-1 inline size-3 text-fg-subtle" aria-hidden />
            </a>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-fg-subtle">
              <span className="font-mono">{source.domain}</span>
              <span>· {humanize(source.source_type)}</span>
              {source.published_at && <span>· {source.published_at.slice(0, 10)}</span>}
              {source.origin === "memory" && <Badge tone="info">memory</Badge>}
              {source.origin === "follow_up" && <Badge>follow-up</Badge>}
              {source.fetch_status === "snippet" && <Badge tone="warning">snippet only</Badge>}
              {source.is_excluded && <Badge tone="danger">excluded</Badge>}
            </div>
          </div>
          <Button
            size="sm"
            variant={source.is_excluded ? "secondary" : "ghost"}
            icon={source.is_excluded ? RotateCcw : Ban}
            loading={busy}
            disabled={locked}
            title={locked ? "Wait until the research finishes" : undefined}
            onClick={async () => {
              setBusy(true);
              try {
                await onToggle(source);
              } finally {
                setBusy(false);
              }
            }}
          >
            {source.is_excluded ? "Include" : "Exclude"}
          </Button>
        </div>

        <p className={cn("mt-3 text-sm leading-relaxed text-fg-muted", fullText === null && "line-clamp-3")}>{source.excerpt}</p>
        {fullText !== null && (
          <div className="mt-3 max-h-80 overflow-y-auto whitespace-pre-line rounded-lg border border-line bg-surface-2 p-3 text-sm leading-relaxed">
            {fullText}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-3">
          <details className="group min-w-[12rem] flex-1">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-xs text-fg-muted">
              <span>Relevance</span>
              <Meter value={source.relevance_score} className="w-24" label="Relevance" />
              <span className="font-mono">{percent(source.relevance_score)}</span>
              <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <dl className="mt-2 grid max-w-sm gap-1.5 text-xs">
              {FACTORS.filter(([key]) => typeof factors[key] === "number").map(([key, label]) => (
                <div key={key} className="grid grid-cols-[10rem_1fr_2.5rem] items-center gap-2">
                  <dt className="text-fg-subtle">{label}</dt>
                  <dd>
                    <Meter value={factors[key] as number} label={label} />
                  </dd>
                  <dd className="text-right font-mono text-fg-muted">{percent(factors[key] as number)}</dd>
                </div>
              ))}
              {typeof factors.memory_similarity === "number" && (
                <div className="text-fg-subtle">Memory similarity: {percent(factors.memory_similarity)}</div>
              )}
              {source.evaluation_notes.map((note) => (
                <div key={note} className="text-fg-subtle">
                  {note}
                </div>
              ))}
              {source.origin_query && <div className="text-fg-subtle">Found with: “{source.origin_query}”</div>}
            </dl>
          </details>
          {source.content_length > source.excerpt.length && (
            <Button size="sm" variant="ghost" icon={BookOpen} loading={loadingText} onClick={loadFullText}>
              {fullText === null ? "Read full text" : "Hide full text"}
            </Button>
          )}
        </div>
      </Card>
    </li>
  );
}

export function SourcesTab({
  detail,
  index,
  highlightId,
  onToggleExcluded,
  onResynthesize,
}: {
  detail: ResearchDetail;
  index: SourceIndex;
  highlightId: string | null;
  onToggleExcluded: (source: Source) => Promise<void>;
  onResynthesize: () => Promise<void>;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("report");
  const running = !isTerminal(detail.status);

  const citedIds = index.numberById;
  const sorted = useMemo(() => {
    const list = [...detail.sources];
    if (sort === "relevance") return list.sort((a, b) => b.relevance_score - a.relevance_score);
    return list.sort((a, b) => (citedIds.get(a.id) ?? 999) - (citedIds.get(b.id) ?? 999) || b.relevance_score - a.relevance_score);
  }, [detail.sources, sort, citedIds]);

  if (detail.sources.length === 0) {
    return (
      <EmptyState icon={BookOpen} title="No sources yet">
        Sources appear here as the researcher collects them.
      </EmptyState>
    );
  }

  const active = FILTERS.find((f) => f.key === filter)!;
  const visible = sorted.filter((s) => active.test(s, citedIds.has(s.id)));
  const reportUsesExcluded = detail.report?.citations.some((c) => c.source_id && detail.sources.find((s) => s.id === c.source_id)?.is_excluded);

  return (
    <div className="space-y-4">
      {reportUsesExcluded && !running && (
        <div className="flex flex-col gap-3 rounded-xl border border-warning/30 bg-warning/[0.07] p-4 text-sm sm:flex-row sm:items-center">
          <p className="flex-1 text-fg-muted">You changed the source selection. Regenerate the report to re-verify the claims with the remaining sources.</p>
          <Button variant="primary" size="sm" icon={RefreshCw} onClick={onResynthesize}>
            Regenerate report
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5" role="toolbar" aria-label="Filter sources">
          {FILTERS.map((f) => {
            const count = detail.sources.filter((s) => f.test(s, citedIds.has(s.id))).length;
            if (f.key !== "all" && count === 0) return null;
            return (
              <button
                key={f.key}
                type="button"
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  filter === f.key ? "border-fg bg-fg text-bg" : "border-line bg-surface text-fg-muted hover:text-fg",
                )}
              >
                {f.label} <span className="font-mono opacity-70">{count}</span>
              </button>
            );
          })}
        </div>
        <label className="flex items-center gap-2 text-xs text-fg-muted">
          Sort
          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as Sort)}
            className="rounded-md border border-line bg-surface px-2 py-1 text-xs text-fg"
          >
            <option value="report">Report order</option>
            <option value="relevance">Relevance</option>
          </select>
        </label>
      </div>

      {running && <p className="flex items-center gap-2 text-xs text-fg-muted"><Spinner className="size-3" /> The research is running — this list updates live.</p>}

      <ul className="space-y-3">
        {visible.map((source) => (
          <SourceCard
            key={source.id}
            source={source}
            number={citedIds.get(source.id)}
            researchId={detail.id}
            highlighted={highlightId === source.id}
            locked={running}
            onToggle={onToggleExcluded}
          />
        ))}
      </ul>
    </div>
  );
}
