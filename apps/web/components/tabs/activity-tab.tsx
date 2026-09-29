"use client";

import {
  Activity,
  AlertTriangle,
  Compass,
  Database,
  FileText,
  GitBranch,
  Search,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import { describeEvent } from "@/lib/events";
import { cn, formatDuration } from "@/lib/format";
import { TONE_BADGE, TONE_TEXT } from "@/lib/meta";
import type { ResearchEvent } from "@/lib/types";

import { Card, EmptyState, Spinner } from "../ui";

const AGENT_ICONS: Record<string, LucideIcon> = {
  planner: Compass,
  researcher: Search,
  memory: Database,
  semantic_memory: Database,
  verifier: ShieldCheck,
  gap_analyzer: GitBranch,
  synthesizer: FileText,
  orchestrator: Workflow,
};

export function ActivityTab({ events, live }: { events: ResearchEvent[]; live: boolean }) {
  if (events.length === 0) {
    return (
      <EmptyState icon={Activity} title="No activity yet">
        Agent events stream here in real time.
      </EmptyState>
    );
  }
  const start = new Date(events[0].created_at).getTime();

  return (
    <Card className="p-4 sm:p-6">
      <ol className="relative space-y-4 before:absolute before:bottom-2 before:left-[15px] before:top-2 before:w-px before:bg-line" aria-live="polite">
        {events.map((event) => {
          const view = describeEvent(event);
          const Icon = event.event_type === "warning" ? AlertTriangle : (AGENT_ICONS[event.agent] ?? Activity);
          const offset = (new Date(event.created_at).getTime() - start) / 1000;
          return (
            <li key={event.seq || event.id} className="relative flex animate-fade-in gap-3">
              <span
                className={cn(
                  "relative z-10 grid size-8 shrink-0 place-items-center rounded-full border bg-surface",
                  view.tone === "neutral" ? "border-line text-fg-muted" : TONE_BADGE[view.tone],
                )}
              >
                <Icon className="size-3.5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <div className="flex items-baseline justify-between gap-3">
                  <p className={cn("text-sm font-medium", view.tone !== "neutral" && TONE_TEXT[view.tone])}>{view.title}</p>
                  <span className="shrink-0 font-mono text-[11px] text-fg-subtle">+{formatDuration(Math.max(offset, 0))}</span>
                </div>
                {view.detail && <p className="mt-0.5 break-words text-xs leading-relaxed text-fg-muted">{view.detail}</p>}
                <details className="mt-1">
                  <summary className="cursor-pointer text-[11px] text-fg-subtle hover:text-fg-muted">
                    {event.agent} · {event.event_type}
                  </summary>
                  <pre className="mt-1.5 max-h-60 overflow-auto rounded-lg border border-line bg-surface-2 p-2.5 font-mono text-[11px] leading-relaxed text-fg-muted">
                    {JSON.stringify(event.data, null, 2)}
                  </pre>
                </details>
              </div>
            </li>
          );
        })}
        {live && (
          <li className="relative flex items-center gap-3 text-xs text-fg-muted">
            <span className="relative z-10 grid size-8 place-items-center rounded-full border border-line bg-surface">
              <Spinner className="size-3.5" />
            </span>
            Listening for agent events…
          </li>
        )}
      </ol>
    </Card>
  );
}
