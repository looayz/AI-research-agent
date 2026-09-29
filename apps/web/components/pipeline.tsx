"use client";

import { Check, Compass, FileText, GitBranch, Minus, Search, ShieldCheck, X } from "lucide-react";

import { derivePipeline, STEPS, type StepKey, type StepState } from "@/lib/events";
import { cn } from "@/lib/format";
import type { Depth, ResearchEvent } from "@/lib/types";

import { Spinner } from "./ui";

const ICONS: Record<StepKey, typeof Compass> = {
  plan: Compass,
  retrieve: Search,
  verify: ShieldCheck,
  deepen: GitBranch,
  synthesize: FileText,
};

const STATE_LABEL: Record<StepState, string> = {
  pending: "Pending",
  active: "In progress",
  done: "Done",
  skipped: "Skipped",
  failed: "Stopped",
};

function StepIcon({ state, step }: { state: StepState; step: StepKey }) {
  const Icon = ICONS[step];
  if (state === "active") return <Spinner className="size-3.5" />;
  if (state === "done") return <Check className="size-3.5" aria-hidden />;
  if (state === "failed") return <X className="size-3.5" aria-hidden />;
  if (state === "skipped") return <Minus className="size-3.5" aria-hidden />;
  return <Icon className="size-3.5" aria-hidden />;
}

export function Pipeline({ events, depth, running }: { events: ResearchEvent[]; depth: Depth; running: boolean }) {
  const pipeline = derivePipeline(events, depth);
  const currentIndex = (() => {
    const active = STEPS.findIndex((s) => ["active", "failed"].includes(pipeline[s.key].state));
    if (active >= 0) return active;
    const done = STEPS.map((s) => pipeline[s.key].state).lastIndexOf("done");
    return Math.max(done, 0);
  })();
  const current = STEPS[currentIndex];
  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-surface">
      {running && (
        <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden bg-muted" aria-hidden>
          <div className="h-full w-1/3 animate-[slide_1.4s_ease-in-out_infinite] bg-fg/60" />
        </div>
      )}
      <ol className="grid grid-cols-5 divide-x divide-line">
        {STEPS.map((step, index) => {
          const { state, detail } = pipeline[step.key];
          return (
            <li
              key={step.key}
              className={cn(
                "flex min-w-0 flex-col items-center gap-1.5 px-1 py-3 sm:items-stretch sm:px-3.5",
                state === "skipped" && "opacity-55",
              )}
              aria-current={state === "active" ? "step" : undefined}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid size-6 shrink-0 place-items-center rounded-full border text-[11px]",
                    state === "done" && "border-success/30 bg-success/10 text-success",
                    state === "active" && "border-fg bg-fg text-bg",
                    state === "failed" && "border-danger/30 bg-danger/10 text-danger",
                    (state === "pending" || state === "skipped") && "border-line bg-surface-2 text-fg-subtle",
                  )}
                >
                  <StepIcon state={state} step={step.key} />
                </span>
                <span className={cn("hidden truncate text-xs font-medium sm:inline", state === "pending" ? "text-fg-subtle" : "text-fg")}>
                  <span className="hidden font-mono text-fg-subtle sm:inline">{index + 1}. </span>
                  {step.label}
                </span>
              </div>
              <p className="hidden truncate text-[11px] text-fg-muted sm:block" title={detail}>
                {detail ?? STATE_LABEL[state]}
              </p>
              <span className="sr-only">{STATE_LABEL[state]}</span>
            </li>
          );
        })}
      </ol>
      <p className="border-t border-line px-3 py-2 text-[11px] text-fg-muted sm:hidden">
        <span className="font-medium text-fg">
          {currentIndex + 1}/5 · {current.label}
        </span>
        {" — "}
        {pipeline[current.key].detail ?? STATE_LABEL[pipeline[current.key].state]}
      </p>
    </div>
  );
}
