"use client";

import { Scale } from "lucide-react";

import type { SourceIndex, SourceRef } from "@/lib/sources";
import type { ResearchDetail } from "@/lib/types";

import { SourceChip } from "../source-chip";
import { Card, EmptyState } from "../ui";

function Side({ label, point, url, index, onOpenSource }: {
  label: string;
  point: string;
  url: string;
  index: SourceIndex;
  onOpenSource: (ref: SourceRef) => void;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface-2 p-3.5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">{label}</span>
      <p className="flex-1 text-sm leading-relaxed">{point}</p>
      {url && (
        <div>
          <SourceChip refInfo={index.resolve(url)} onOpen={onOpenSource} />
        </div>
      )}
    </div>
  );
}

export function ContradictionsTab({
  detail,
  index,
  onOpenSource,
}: {
  detail: ResearchDetail;
  index: SourceIndex;
  onOpenSource: (ref: SourceRef) => void;
}) {
  if (detail.contradictions.length === 0) {
    return (
      <EmptyState icon={Scale} title="No contradictions detected">
        When sources disagree on a specific point, the verifier lists both positions here with the most likely reason.
      </EmptyState>
    );
  }
  return (
    <ul className="space-y-3">
      {detail.contradictions.map((item) => (
        <li key={item.id}>
          <Card className="p-4 sm:p-5">
            <div className="mb-3 flex items-center gap-2">
              <Scale className="size-4 text-warning" aria-hidden />
              <h3 className="text-sm font-semibold">{item.topic}</h3>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Side label="Position A" point={item.point_a} url={item.source_a_url} index={index} onOpenSource={onOpenSource} />
              <Side label="Position B" point={item.point_b} url={item.source_b_url} index={index} onOpenSource={onOpenSource} />
            </div>
            {item.explanation && (
              <p className="mt-3 text-sm text-fg-muted">
                <span className="font-medium text-fg">Why they differ: </span>
                {item.explanation}
              </p>
            )}
          </Card>
        </li>
      ))}
    </ul>
  );
}
