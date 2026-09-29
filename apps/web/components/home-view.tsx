"use client";

import { ArrowRight, ArrowUpRight, FlaskConical, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn, plural, timeAgo } from "@/lib/format";
import { useHotkey } from "@/lib/hooks";
import { DEPTHS, DOMAINS } from "@/lib/meta";
import type { Depth, Domain, Health, ResearchSummary } from "@/lib/types";

import { Badge, Button, Card, Kbd, Segmented } from "./ui";

const EXAMPLES: { domain: Domain; question: string }[] = [
  { domain: "general", question: "What are the main arguments for and against a four-day work week, and what do trials show?" },
  { domain: "academic", question: "Does spaced repetition improve long-term retention compared with massed practice?" },
  { domain: "technical", question: "What are the trade-offs of migrating TLS to post-quantum key exchange (ML-KEM)?" },
  { domain: "market", question: "How big is the home battery storage market in Europe and who are the leading players?" },
];

const MIN_LENGTH = 5;
const MAX_LENGTH = 2000;

export function Composer({
  onSubmit,
  initialQuestion = "",
  initialDomain = "general",
  autoFocus,
}: {
  onSubmit: (payload: { question: string; depth: Depth; domain: Domain }) => Promise<void>;
  initialQuestion?: string;
  initialDomain?: Domain;
  autoFocus?: boolean;
}) {
  const [question, setQuestion] = useState(initialQuestion);
  const [domain, setDomain] = useState<Domain>(initialDomain);
  const [depth, setDepth] = useState<Depth>("standard");
  const [submitting, setSubmitting] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 260)}px`;
  }, [question]);

  useHotkey("/", (event) => {
    event.preventDefault();
    textarea.current?.focus();
  });

  const trimmed = question.trim();
  const valid = trimmed.length >= MIN_LENGTH && trimmed.length <= MAX_LENGTH;

  const submit = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      await onSubmit({ question: trimmed, depth, domain });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-2 focus-within:border-line-strong focus-within:shadow-md">
      <label htmlFor="question" className="sr-only">
        Research question
      </label>
      <textarea
        id="question"
        ref={textarea}
        value={question}
        autoFocus={autoFocus}
        rows={3}
        maxLength={MAX_LENGTH}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            void submit();
          }
        }}
        placeholder="Ask a complex question: the agents will plan, search, verify claims and write a cited report…"
        className="block w-full resize-none bg-transparent px-3 py-2.5 text-[15px] leading-relaxed text-fg placeholder:text-fg-subtle focus:outline-none"
      />
      <div className="flex flex-wrap items-center gap-2 border-t border-line px-1.5 pt-2">
        <Segmented
          label="Research profile"
          value={domain}
          onChange={setDomain}
          options={(Object.keys(DOMAINS) as Domain[]).map((key) => ({
            value: key,
            label: DOMAINS[key].label,
            icon: DOMAINS[key].icon,
            hint: DOMAINS[key].hint,
          }))}
        />
        <Segmented
          label="Research depth"
          value={depth}
          onChange={setDepth}
          options={(Object.keys(DEPTHS) as Depth[]).map((key) => ({ value: key, label: DEPTHS[key].label, hint: DEPTHS[key].hint }))}
        />
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden text-[11px] text-fg-subtle sm:inline">
            <Kbd>Ctrl</Kbd> <Kbd>Enter</Kbd>
          </span>
          <Button variant="primary" onClick={submit} disabled={!valid} loading={submitting}>
            Start research <ArrowRight className="size-4" aria-hidden />
          </Button>
        </div>
      </div>
      <p className="px-3 pb-1 pt-2 text-[11px] text-fg-subtle">
        {DOMAINS[domain].hint} · {DEPTHS[depth].hint}
        {question.length > MAX_LENGTH - 200 && ` · ${question.length}/${MAX_LENGTH}`}
      </p>
    </Card>
  );
}

function DemoNotice({ health }: { health: Health }) {
  return (
    <div className="flex gap-3 rounded-xl border border-warning/30 bg-warning/[0.07] p-4 text-sm">
      <FlaskConical className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
      <div className="space-y-1 text-fg-muted">
        <p className="font-medium text-fg">Demo mode: the agents run on offline mock providers.</p>
        <p>
          Reports are generated from synthetic sources so you can try the whole pipeline for free. For real research, set{" "}
          <code className="rounded bg-muted px-1 font-mono text-xs">LLM_PROVIDER</code> (openai, anthropic, gemini, groq, ollama…) and{" "}
          <code className="rounded bg-muted px-1 font-mono text-xs">SEARCH_PROVIDER</code> (wikipedia and duckduckgo need no key) in{" "}
          <code className="rounded bg-muted px-1 font-mono text-xs">.env</code>.
        </p>
        {health.mock_mode && <p className="text-xs">MOCK_MODE=true forces demo providers even when others are configured.</p>}
      </div>
    </div>
  );
}

export function HomeView({
  health,
  recent,
  onSubmit,
  onOpen,
}: {
  health: Health | null;
  recent: ResearchSummary[];
  onSubmit: (payload: { question: string; depth: Depth; domain: Domain }) => Promise<void>;
  onOpen: (id: string) => void;
}) {
  const [seed, setSeed] = useState<{ key: number; question: string; domain: Domain } | null>(null);
  const completed = recent.filter((r) => r.status === "completed").slice(0, 3);

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-16 pt-10 sm:px-6 sm:pt-16">
      <div className="mb-7 text-center">
        <Badge tone="neutral" className="mb-4">
          <Sparkles className="size-3" aria-hidden /> Plan · Search · Verify · Synthesize
        </Badge>
        <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">What do you want to investigate?</h1>
        <p className="mx-auto mt-3 max-w-xl text-balance text-[15px] text-fg-muted">
          Autonomous agents break your question down, collect sources, cross-check every claim and write a report where each
          statement links back to its evidence.
        </p>
      </div>

      <Composer key={seed?.key ?? 0} initialQuestion={seed?.question} initialDomain={seed?.domain} onSubmit={onSubmit} autoFocus />

      {health?.demo_mode && (
        <div className="mt-4">
          <DemoNotice health={health} />
        </div>
      )}

      <section className="mt-10" aria-labelledby="examples-title">
        <h2 id="examples-title" className="mb-3 text-xs font-medium uppercase tracking-wider text-fg-subtle">
          Try an example
        </h2>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {EXAMPLES.map((example) => {
            const Icon = DOMAINS[example.domain].icon;
            return (
              <button
                key={example.question}
                type="button"
                onClick={() => setSeed({ key: Date.now(), question: example.question, domain: example.domain })}
                className="group flex items-start gap-3 rounded-xl border border-line bg-surface p-3.5 text-left text-sm transition-colors hover:border-line-strong hover:bg-surface-2"
              >
                <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-muted text-fg-muted group-hover:text-fg">
                  <Icon className="size-3.5" aria-hidden />
                </span>
                <span className="text-fg-muted group-hover:text-fg">{example.question}</span>
              </button>
            );
          })}
        </div>
      </section>

      {completed.length > 0 && (
        <section className="mt-10" aria-labelledby="recent-title">
          <h2 id="recent-title" className="mb-3 text-xs font-medium uppercase tracking-wider text-fg-subtle">
            Recent reports
          </h2>
          <div className="grid gap-2.5">
            {completed.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onOpen(item.id)}
                className={cn(
                  "group rounded-xl border border-line bg-surface p-4 text-left transition-colors hover:border-line-strong hover:bg-surface-2",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium">{item.report_title || item.question}</p>
                  <ArrowUpRight className="size-4 shrink-0 text-fg-subtle group-hover:text-fg" aria-hidden />
                </div>
                {item.executive_summary && <p className="mt-1 line-clamp-2 text-sm text-fg-muted">{item.executive_summary}</p>}
                <p className="mt-2 text-xs text-fg-subtle">
                  {DOMAINS[item.domain].label} · {DEPTHS[item.depth].label} · {plural(item.source_count, "source")} · {timeAgo(item.created_at)}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
