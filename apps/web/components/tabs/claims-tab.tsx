"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { cn, percent } from "@/lib/format";
import { CLAIM_ORDER, CLAIM_STATUS, TONE_BADGE } from "@/lib/meta";
import type { SourceIndex, SourceRef } from "@/lib/sources";
import type { ClaimStatus, ResearchDetail } from "@/lib/types";

import { SourceChip } from "../source-chip";
import { Badge, Card, EmptyState, Meter } from "../ui";

export function ClaimsTab({
  detail,
  index,
  onOpenSource,
}: {
  detail: ResearchDetail;
  index: SourceIndex;
  onOpenSource: (ref: SourceRef) => void;
}) {
  const [filter, setFilter] = useState<ClaimStatus | "all">("all");
  const claims = filter === "all" ? detail.claims : detail.claims.filter((c) => c.status === filter);

  if (detail.claims.length === 0) {
    return (
      <EmptyState icon={ShieldCheck} title="No verified claims yet">
        Claims appear here as soon as the verifier has cross-checked the collected sources.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5" role="toolbar" aria-label="Filter claims by status">
        {(["all", ...CLAIM_ORDER] as const).map((status) => {
          const count = status === "all" ? detail.claims.length : detail.claims.filter((c) => c.status === status).length;
          if (status !== "all" && count === 0) return null;
          const active = filter === status;
          return (
            <button
              key={status}
              type="button"
              aria-pressed={active}
              onClick={() => setFilter(status)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                active ? "border-fg bg-fg text-bg" : "border-line bg-surface text-fg-muted hover:text-fg",
              )}
            >
              {status === "all" ? "All" : CLAIM_STATUS[status].label} <span className="font-mono opacity-70">{count}</span>
            </button>
          );
        })}
      </div>

      <ul className="space-y-3">
        {claims.map((claim) => {
          const meta = CLAIM_STATUS[claim.status];
          const Icon = meta.icon;
          return (
            <li key={claim.id}>
              <Card className="p-4 sm:p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className={cn("inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium", TONE_BADGE[meta.tone])}>
                    <Icon className="size-3.5" aria-hidden /> {meta.label}
                  </span>
                  <div className="flex w-40 items-center gap-2" title="Verifier confidence">
                    <Meter value={claim.confidence} tone={meta.tone} label="Confidence" />
                    <span className="w-9 text-right font-mono text-xs text-fg-muted">{percent(claim.confidence)}</span>
                  </div>
                </div>
                <p className="mt-3 text-[15px] font-medium leading-relaxed">{claim.claim_text}</p>
                {claim.reasoning && <p className="mt-1.5 text-sm leading-relaxed text-fg-muted">{claim.reasoning}</p>}
                {(claim.supporting_sources.length > 0 || claim.contradicting_sources.length > 0) && (
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
                    {claim.supporting_sources.length > 0 && <Badge tone="success">supports</Badge>}
                    {claim.supporting_sources.map((url) => (
                      <SourceChip key={url} refInfo={index.resolve(url)} onOpen={onOpenSource} />
                    ))}
                    {claim.contradicting_sources.length > 0 && (
                      <Badge tone="danger" className="ml-1">
                        contradicts
                      </Badge>
                    )}
                    {claim.contradicting_sources.map((url) => (
                      <SourceChip key={url} refInfo={index.resolve(url)} tone="danger" onOpen={onOpenSource} />
                    ))}
                  </div>
                )}
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
