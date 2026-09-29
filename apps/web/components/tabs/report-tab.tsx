"use client";

import { AlertTriangle, Check, Copy, ExternalLink, FileText, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";

import { describeEvent } from "@/lib/events";
import { cn, formatDate, plural, safeHref } from "@/lib/format";
import { CLAIM_ORDER, CLAIM_STATUS, TONE_BAR } from "@/lib/meta";
import type { Citation, ResearchDetail, ResearchEvent } from "@/lib/types";
import { isTerminal } from "@/lib/types";

import { Markdown } from "../markdown";
import { Badge, Button, Card, EmptyState, Spinner, useToast } from "../ui";

const normalize = (text: string) =>
  text
    .toLowerCase()
    .replace(/\[\d+\]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, "");

/** The summary is shown in its own card: drop the duplicated first section from the body. */
export function withoutSummarySection(markdown: string, summary: string): string {
  const match = markdown.match(/^(#\s[^\n]*\n+)?##\s[^\n]*\n([\s\S]*?)(?=\n##\s|$)/);
  if (!match || !summary) return markdown;
  const probe = normalize(summary).slice(0, 40);
  if (!probe || !normalize(match[2]).includes(probe)) return markdown;
  return markdown.replace(match[0], match[1] ?? "");
}

function EvidenceSummary({ detail }: { detail: ResearchDetail }) {
  const total = detail.claims.length;
  const counts = CLAIM_ORDER.map((status) => ({ status, count: detail.claims.filter((c) => c.status === status).length }));
  const cited = detail.report?.citations.filter((c) => c.cited).length ?? 0;
  return (
    <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
      <div>
        <div className="mb-2 flex items-baseline justify-between text-xs">
          <span className="font-medium text-fg">Evidence check</span>
          <span className="text-fg-subtle">{plural(total, "claim")} verified</span>
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
          {counts.map(({ status, count }) =>
            count ? <div key={status} className={TONE_BAR[CLAIM_STATUS[status].tone]} style={{ width: `${(count / total) * 100}%` }} /> : null,
          )}
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fg-muted">
          {counts
            .filter(({ count }) => count > 0)
            .map(({ status, count }) => (
            <li key={status} className="flex items-center gap-1.5">
              <span className={cn("size-2 rounded-full", TONE_BAR[CLAIM_STATUS[status].tone])} aria-hidden />
              {count} {CLAIM_STATUS[status].short.toLowerCase()}
            </li>
          ))}
        </ul>
      </div>
      <dl className="flex gap-6 text-right">
        <div>
          <dt className="text-[11px] text-fg-subtle">Sources cited</dt>
          <dd className="font-mono text-lg font-semibold">
            {cited}
            <span className="text-sm font-normal text-fg-subtle">/{detail.report?.citations.length ?? 0}</span>
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-fg-subtle">Contradictions</dt>
          <dd className="font-mono text-lg font-semibold">{detail.contradictions.length}</dd>
        </div>
      </dl>
    </div>
  );
}

function WaitingForReport({ detail, events }: { detail: ResearchDetail; events: ResearchEvent[] }) {
  if (isTerminal(detail.status)) {
    return (
      <EmptyState icon={FileText} title="No report">
        {detail.status === "failed" ? "The research stopped before the report was written." : "The research was cancelled before the report was written."}
      </EmptyState>
    );
  }
  const latest = events.slice(-4).reverse();
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3">
        <Spinner />
        <p className="text-sm font-medium">The report is written once the evidence has been collected and verified…</p>
      </div>
      <div className="mt-5 space-y-3" aria-hidden>
        {[92, 78, 85, 60].map((width, i) => (
          <div key={i} className="h-3 animate-pulse rounded bg-muted" style={{ width: `${width}%` }} />
        ))}
      </div>
      {latest.length > 0 && (
        <ul className="mt-6 space-y-1.5 border-t border-line pt-4 text-xs text-fg-muted">
          {latest.map((event) => (
            <li key={event.seq} className="animate-fade-in truncate">
              {describeEvent(event).title}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ReportTab({
  detail,
  events,
  onResynthesize,
  onOpenSource,
}: {
  detail: ResearchDetail;
  events: ResearchEvent[];
  onResynthesize: () => Promise<void>;
  onOpenSource: (sourceId: string) => void;
}) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const [flashIndex, setFlashIndex] = useState<number | null>(null);
  const references = useRef<HTMLDivElement>(null);
  const report = detail.report;

  if (!report) return <WaitingForReport detail={detail} events={events} />;

  const excludedIds = new Set(detail.sources.filter((s) => s.is_excluded).map((s) => s.id));
  const staleCitations = report.citations.filter((c) => c.source_id && excludedIds.has(c.source_id));
  const running = !isTerminal(detail.status);
  const notes = report.limitations.filter((item) => !report.markdown_content.includes(item.slice(0, 40)));

  const renderCitation = (citation: Citation) => {
    const href = safeHref(citation.url);
    const excluded = !!citation.source_id && excludedIds.has(citation.source_id);
    return (
      <li
        key={citation.index}
        data-cite={citation.index}
        onAnimationEnd={() => setFlashIndex(null)}
        className={cn(
          "flex items-start gap-3 rounded-lg px-2 py-1.5 text-sm",
          flashIndex === citation.index && "animate-flash",
          !citation.cited && "opacity-70",
        )}
      >
        <span className="mt-0.5 w-7 shrink-0 font-mono text-xs font-semibold text-fg-subtle">[{citation.index}]</span>
        <div className="min-w-0 flex-1">
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={cn("font-medium text-fg hover:underline", excluded && "line-through")}
          >
            {citation.title}
            <ExternalLink className="ml-1 inline size-3 text-fg-subtle" aria-hidden />
          </a>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-fg-subtle">
            <span>{citation.domain}</span>
            {citation.source_type && <span>· {citation.source_type.replace(/_/g, " ")}</span>}
            {!citation.cited && <Badge>not cited</Badge>}
            {excluded && <Badge tone="warning">excluded</Badge>}
            {citation.source_id && (
              <button
                type="button"
                onClick={() => onOpenSource(citation.source_id!)}
                className="no-print text-fg-muted underline-offset-2 hover:text-fg hover:underline"
              >
                details
              </button>
            )}
          </div>
        </div>
      </li>
    );
  };

  const citedRefs = report.citations.filter((c) => c.cited !== false);
  const otherRefs = report.citations.filter((c) => c.cited === false);

  const scrollToCitation = (n: number) => {
    const target = references.current?.querySelector<HTMLElement>(`[data-cite="${n}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashIndex(null);
    window.requestAnimationFrame(() => setFlashIndex(n));
  };

  const copyMarkdown = async () => {
    try {
      await navigator.clipboard.writeText(report.markdown_content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast("Copy failed: clipboard not available", "danger");
    }
  };

  return (
    <div className="space-y-4">
      {staleCitations.length > 0 && (
        <div className="no-print flex flex-col gap-3 rounded-xl border border-warning/30 bg-warning/[0.07] p-4 text-sm sm:flex-row sm:items-center">
          <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden />
          <p className="flex-1 text-fg-muted">
            This report still relies on {staleCitations.length} source{staleCitations.length > 1 ? "s" : ""} you excluded. Regenerate it to
            re-verify the claims without {staleCitations.length > 1 ? "them" : "it"}.
          </p>
          <Button variant="primary" size="sm" icon={RefreshCw} onClick={onResynthesize} disabled={running}>
            Regenerate report
          </Button>
        </div>
      )}

      <Card className="p-5 sm:p-6">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Executive summary</p>
        <p className="text-[15px] leading-7 text-fg">{report.executive_summary}</p>
        {detail.claims.length > 0 && (
          <div className="mt-5 border-t border-line pt-5">
            <EvidenceSummary detail={detail} />
          </div>
        )}
      </Card>

      <Card className="print-full p-5 sm:p-8">
        <div className="no-print mb-4 flex items-center justify-between gap-3 text-xs text-fg-subtle">
          <span>Generated {formatDate(report.created_at)}</span>
          <Button size="sm" variant="ghost" icon={copied ? Check : Copy} onClick={copyMarkdown}>
            {copied ? "Copied" : "Copy Markdown"}
          </Button>
        </div>
        <Markdown
          content={withoutSummarySection(report.markdown_content, report.executive_summary)}
          citations={report.citations}
          onCite={scrollToCitation}
        />

        {notes.length > 0 && (
          <div className="mt-8 rounded-lg border border-line bg-surface-2 p-4">
            <p className="mb-2 text-xs font-medium text-fg">Notes</p>
            <ul className="list-disc space-y-1 pl-4 text-sm text-fg-muted">
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}

        <div ref={references} className="mt-10 border-t border-line pt-6">
          <h2 className="mb-3 text-sm font-semibold">References</h2>
          <ol className="space-y-1.5">
            {citedRefs.map(renderCitation)}
          </ol>
          {otherRefs.length > 0 && (
            <details className="mt-3" open={otherRefs.some((c) => c.index === flashIndex) || undefined}>
              <summary className="cursor-pointer px-2 text-xs text-fg-muted hover:text-fg">
                {plural(otherRefs.length, "other source")} consulted but not cited
              </summary>
              <ol className="mt-2 space-y-1.5">{otherRefs.map(renderCitation)}</ol>
            </details>
          )}
        </div>
      </Card>
    </div>
  );
}
