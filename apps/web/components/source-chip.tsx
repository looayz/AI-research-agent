"use client";

import { cn, hostname } from "@/lib/format";
import type { SourceRef } from "@/lib/sources";

export function SourceChip({
  refInfo,
  tone = "neutral",
  onOpen,
}: {
  refInfo: SourceRef;
  tone?: "neutral" | "danger";
  onOpen?: (ref: SourceRef) => void;
}) {
  const label = refInfo.source?.domain ?? hostname(refInfo.url);
  return (
    <button
      type="button"
      onClick={() => onOpen?.(refInfo)}
      title={refInfo.source?.title ?? refInfo.url}
      className={cn(
        "inline-flex max-w-[16rem] items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[11px] transition-colors",
        tone === "danger"
          ? "border-danger/25 bg-danger/[0.06] text-danger hover:bg-danger/10"
          : "border-line bg-surface-2 text-fg-muted hover:border-line-strong hover:text-fg",
        refInfo.source?.is_excluded && "line-through opacity-60",
      )}
    >
      {refInfo.number !== undefined && <span className="font-mono font-semibold">[{refInfo.number}]</span>}
      <span className="truncate">{label}</span>
    </button>
  );
}
