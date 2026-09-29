import { formatDuration, formatNumber, humanize, plural } from "./format";
import type { Tone } from "./meta";
import type { Depth, ResearchEvent } from "./types";

export type StepKey = "plan" | "retrieve" | "verify" | "deepen" | "synthesize";
export type StepState = "pending" | "active" | "done" | "skipped" | "failed";

export const STEPS: { key: StepKey; label: string }[] = [
  { key: "plan", label: "Plan" },
  { key: "retrieve", label: "Retrieve" },
  { key: "verify", label: "Verify" },
  { key: "deepen", label: "Deepen" },
  { key: "synthesize", label: "Synthesize" },
];

export type Pipeline = Record<StepKey, { state: StepState; detail?: string }>;

/** Folds the event log into the state of each pipeline step. */
export function derivePipeline(events: ResearchEvent[], depth: Depth): Pipeline {
  const pipeline: Pipeline = {
    plan: { state: "pending" },
    retrieve: { state: "pending" },
    verify: { state: "pending" },
    deepen: depth === "quick" ? { state: "skipped", detail: "Not used in quick mode" } : { state: "pending" },
    synthesize: { state: "pending" },
  };
  let deepening = false;
  const activate = (key: StepKey, detail?: string) => {
    pipeline[key] = { state: "active", detail: detail ?? pipeline[key].detail };
  };
  const finish = (key: StepKey, detail?: string) => {
    pipeline[key] = { state: "done", detail: detail ?? pipeline[key].detail };
  };

  for (const { event_type: type, data } of events) {
    switch (type) {
      case "research.started":
        if (data.mode === "resynthesize") {
          pipeline.verify = { state: "pending" };
          pipeline.synthesize = { state: "pending" };
          deepening = false;
        }
        break;
      case "planner.started":
        activate("plan");
        break;
      case "planner.completed":
        finish("plan", `${plural(data.queries?.length ?? 0, "query", "queries")}`);
        break;
      case "memory.recalled":
      case "semantic_memory.matched":
        activate("retrieve", `${data.count ?? data.matched_count ?? 0} from memory`);
        break;
      case "search.started":
        if ((data.iteration ?? 0) > 0) activate("deepen", `Follow-up search · round ${data.iteration}`);
        else activate("retrieve", `Searching ${plural(data.queries?.length ?? data.count ?? 0, "query", "queries")}`);
        break;
      case "search.completed":
        if ((data.iteration ?? 0) === 0) finish("retrieve", plural(data.total_sources ?? data.new_sources ?? 0, "source"));
        else pipeline.deepen.detail = `+${plural(data.new_sources ?? 0, "source")}`;
        break;
      case "sources.collected":
        finish("retrieve", plural(data.total_sources ?? 0, "source"));
        break;
      case "verifier.started":
        if (deepening) activate("deepen", "Re-verifying with new evidence");
        else activate("verify");
        break;
      case "verifier.completed":
        if (!deepening) finish("verify", plural(data.claims ?? data.claims_count ?? 0, "claim"));
        break;
      case "gap_analyzer.started":
        deepening = true;
        activate("deepen", data.round ? `Gap analysis · round ${data.round}/${data.max_rounds}` : "Gap analysis");
        break;
      case "gap_analyzer.completed":
        pipeline.deepen.detail = data.sufficient ? "Evidence sufficient" : plural(data.follow_up_queries?.length ?? 0, "follow-up query", "follow-up queries");
        break;
      case "follow_up.started":
        deepening = true;
        activate("deepen", "Follow-up search");
        break;
      case "synthesizer.started":
        if (pipeline.deepen.state === "active") finish("deepen");
        else if (pipeline.deepen.state === "pending") pipeline.deepen = { state: "skipped", detail: "Not needed" };
        activate("synthesize");
        break;
      case "synthesizer.completed":
        finish("synthesize", data.words ? `${formatNumber(data.words)} words` : undefined);
        break;
      case "research.completed":
        for (const step of STEPS) {
          if (pipeline[step.key].state === "active") finish(step.key);
          if (pipeline[step.key].state === "pending") pipeline[step.key] = { state: "skipped" };
        }
        break;
      case "research.failed":
      case "research.cancelled": {
        const active = STEPS.find((s) => pipeline[s.key].state === "active");
        if (active) {
          pipeline[active.key] = { state: "failed", detail: type === "research.cancelled" ? "Cancelled" : "Failed" };
        }
        break;
      }
    }
  }
  return pipeline;
}

export interface EventView {
  title: string;
  detail?: string;
  tone: Tone;
}

export function describeEvent({ event_type: type, data }: ResearchEvent): EventView {
  switch (type) {
    case "research.started":
      return {
        title: data.mode === "resynthesize" ? "Regenerating the report" : "Research started",
        detail: data.llm ? `LLM ${data.llm} · search ${data.search}` : undefined,
        tone: "neutral",
      };
    case "planner.started":
      return { title: "Planning the investigation", tone: "neutral" };
    case "planner.completed":
      return {
        title: data.fallback ? "Fallback plan (planner output unusable)" : "Plan ready",
        detail: `${plural(data.sub_questions?.length ?? 0, "sub-question")} · ${plural(data.queries?.length ?? 0, "search query", "search queries")}`,
        tone: data.fallback ? "warning" : "neutral",
      };
    case "memory.recalled":
    case "semantic_memory.matched":
      return {
        title: `Recalled ${plural(data.count ?? data.matched_count ?? 0, "source")} from memory`,
        detail: (data.matches ?? []).map((m: { title: string }) => m.title).join(" · "),
        tone: "info",
      };
    case "search.started":
      return {
        title: (data.iteration ?? 0) > 0 ? `Follow-up search · round ${data.iteration}` : "Searching the web",
        detail: (data.queries ?? []).join(" · "),
        tone: "neutral",
      };
    case "search.completed": {
      const failed = data.failed_fetches ? ` · ${plural(data.failed_fetches, "page")} unreachable` : "";
      const errors = data.errors?.length ? ` · ${data.errors[0]}` : "";
      return {
        title: `Collected ${plural(data.new_sources ?? 0, "new source")}`,
        detail: `${plural(data.results ?? 0, "search result")}${failed}${errors}`,
        tone: data.errors?.length ? "warning" : "neutral",
      };
    }
    case "sources.collected":
      return { title: `Collected ${plural(data.total_sources ?? 0, "source")}`, tone: "neutral" };
    case "verifier.started":
      return { title: `Verifying claims against ${plural(data.sources ?? data.sources_to_verify ?? 0, "source")}`, tone: "neutral" };
    case "verifier.completed": {
      const byStatus = Object.entries(data.by_status ?? {})
        .map(([status, n]) => `${n} ${humanize(status).toLowerCase()}`)
        .join(" · ");
      return {
        title: `${plural(data.claims ?? data.claims_count ?? 0, "claim")} checked, ${plural(data.contradictions ?? data.contradictions_count ?? 0, "contradiction")}`,
        detail: byStatus || undefined,
        tone: "neutral",
      };
    }
    case "gap_analyzer.started":
      return { title: `Looking for evidence gaps${data.round ? ` · round ${data.round}/${data.max_rounds}` : ""}`, tone: "neutral" };
    case "gap_analyzer.completed":
      return data.sufficient
        ? { title: "Evidence judged sufficient", tone: "success" }
        : {
            title: `${plural(data.gaps?.length ?? 0, "gap")} found → ${plural(data.follow_up_queries?.length ?? 0, "follow-up query", "follow-up queries")}`,
            detail: (data.gaps ?? []).join(" · "),
            tone: "neutral",
          };
    case "follow_up.started":
      return { title: "Follow-up search", detail: (data.queries ?? []).join(" · "), tone: "neutral" };
    case "follow_up.completed":
      return { title: `Follow-up found ${plural(data.additional_sources_count ?? 0, "source")}`, tone: "neutral" };
    case "synthesizer.started":
      return { title: `Writing the report from ${plural(data.sources ?? 0, "source")}`, tone: "neutral" };
    case "synthesizer.completed":
      return {
        title: data.title ? `Report written: “${data.title}”` : "Report written",
        detail: data.words ? `${formatNumber(data.words)} words · ${plural(data.cited_sources ?? 0, "source")} cited` : undefined,
        tone: "neutral",
      };
    case "warning":
      return { title: data.message ?? "Warning", tone: "warning" };
    case "research.completed":
      return {
        title: "Research completed",
        detail:
          data.runtime_seconds != null
            ? `${formatDuration(data.runtime_seconds)} · ${formatNumber(data.tokens_used)} tokens · ${plural(data.llm_calls ?? 0, "LLM call")}`
            : undefined,
        tone: "success",
      };
    case "research.failed":
      return { title: "Research failed", detail: data.error, tone: "danger" };
    case "research.cancelled":
      return { title: "Research cancelled", tone: "warning" };
    default:
      return { title: humanize(type.replace(/\./g, " ")), tone: "neutral" };
  }
}
