"use client";

import { ArrowRight, Database, ExternalLink, Search } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/api";
import { humanize, percent, safeHref } from "@/lib/format";
import type { Route } from "@/lib/hooks";
import type { MemoryMatch } from "@/lib/types";

import { Button, Card, EmptyState, Meter, useToast } from "./ui";

export function MemoryView({ navigate }: { navigate: (route: Route) => void }) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryMatch[] | null>(null);
  const [loading, setLoading] = useState(false);

  const search = async () => {
    if (query.trim().length < 2) return;
    setLoading(true);
    try {
      setResults(await api.searchMemory(query.trim()));
    } catch (e) {
      toast((e as Error).message, "danger");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-4 pb-20 pt-8 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Semantic memory</h1>
      <p className="mt-1 max-w-2xl text-sm text-fg-muted">
        Every source collected by past investigations is indexed. New investigations automatically reuse the closest matches;
        you can also search them here. Similarity is lexical (hashed word and bigram vectors computed locally, no external model).
      </p>

      <form
        className="mt-6 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <label className="relative flex-1">
          <span className="sr-only">Search memory</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. post-quantum key exchange performance"
            className="h-10 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm placeholder:text-fg-subtle focus:border-line-strong focus:outline-none"
          />
        </label>
        <Button type="submit" variant="primary" loading={loading} disabled={query.trim().length < 2} className="h-10">
          Search
        </Button>
      </form>

      <div className="mt-6">
        {results === null ? (
          <EmptyState icon={Database} title="Search across everything the agents have read">
            Results show which investigation collected each source.
          </EmptyState>
        ) : results.length === 0 ? (
          <EmptyState icon={Search} title="No similar sources">
            Try different words: matching is based on shared vocabulary.
          </EmptyState>
        ) : (
          <ul className="space-y-3">
            {results.map(({ source, similarity_score, research_question }) => (
              <li key={source.id}>
                <Card className="p-4 sm:p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <a href={safeHref(source.url)} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">
                        {source.title}
                        <ExternalLink className="ml-1 inline size-3 text-fg-subtle" aria-hidden />
                      </a>
                      <p className="mt-0.5 text-xs text-fg-subtle">
                        <span className="font-mono">{source.domain}</span> · {humanize(source.source_type)}
                      </p>
                    </div>
                    <div className="flex w-32 shrink-0 items-center gap-2" title="Similarity with your query">
                      <Meter value={similarity_score} tone="info" label="Similarity" />
                      <span className="w-9 text-right font-mono text-xs text-fg-muted">{percent(similarity_score)}</span>
                    </div>
                  </div>
                  <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-fg-muted">{source.excerpt}</p>
                  {research_question && (
                    <button
                      type="button"
                      onClick={() => navigate({ view: "research", id: source.research_id })}
                      className="mt-3 inline-flex max-w-full items-center gap-1.5 text-xs text-fg-muted hover:text-fg"
                    >
                      <span className="truncate">From: {research_question}</span>
                      <ArrowRight className="size-3 shrink-0" aria-hidden />
                    </button>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
