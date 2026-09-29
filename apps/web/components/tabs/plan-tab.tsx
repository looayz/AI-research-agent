"use client";

import { Compass } from "lucide-react";

import type { ResearchDetail } from "@/lib/types";

import { Badge, Card, EmptyState } from "../ui";

export function PlanTab({ detail }: { detail: ResearchDetail }) {
  const plan = detail.plan;
  if (!plan) {
    return (
      <EmptyState icon={Compass} title="No plan yet">
        The planner decomposes the question into sub-questions and search queries first.
      </EmptyState>
    );
  }
  const rounds = new Map<number, typeof detail.queries>();
  for (const query of detail.queries) rounds.set(query.iteration, [...(rounds.get(query.iteration) ?? []), query]);

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <Card className="space-y-5 p-5 lg:col-span-3">
        <section>
          <h3 className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Objective</h3>
          <p className="mt-1.5 text-[15px] leading-relaxed">{plan.objective}</p>
        </section>
        {plan.sub_questions.length > 0 && (
          <section>
            <h3 className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Sub-questions</h3>
            <ol className="mt-2 space-y-2">
              {plan.sub_questions.map((question, i) => (
                <li key={question} className="flex gap-3 text-sm">
                  <span className="font-mono text-xs text-fg-subtle">{String(i + 1).padStart(2, "0")}</span>
                  <span>{question}</span>
                </li>
              ))}
            </ol>
          </section>
        )}
        {plan.research_scope && (
          <section>
            <h3 className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Scope</h3>
            <p className="mt-1.5 text-sm text-fg-muted">{plan.research_scope}</p>
          </section>
        )}
        {plan.constraints.length > 0 && (
          <section>
            <h3 className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Evidence rules</h3>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-fg-muted">
              {plan.constraints.map((constraint) => (
                <li key={constraint}>{constraint}</li>
              ))}
            </ul>
          </section>
        )}
      </Card>

      <Card className="p-5 lg:col-span-2">
        <h3 className="text-[11px] font-medium uppercase tracking-wider text-fg-subtle">Search queries</h3>
        <div className="mt-3 space-y-4">
          {[...rounds.entries()].map(([iteration, queries]) => (
            <div key={iteration}>
              <p className="mb-1.5 text-xs font-medium text-fg-muted">{iteration === 0 ? "Initial plan" : `Follow-up · round ${iteration}`}</p>
              <ul className="space-y-1.5">
                {queries.map((query) => (
                  <li key={query.id} className="flex items-start justify-between gap-3 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
                    <span className="font-mono text-[13px]">{query.query}</span>
                    <Badge tone={query.results_count ? "neutral" : "warning"} className="shrink-0">
                      {query.results_count} results
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
