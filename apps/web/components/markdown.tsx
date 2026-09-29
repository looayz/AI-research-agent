"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { safeHref } from "@/lib/format";
import type { Citation } from "@/lib/types";

const CITATION_RE = /\[(\d{1,3})\](?!\()/g;
const CODE_SPLIT_RE = /(```[\s\S]*?```|`[^`\n]*`)/g;

/** Turns [n] citations into links (outside code) so they can be rendered as chips. */
export function linkCitations(markdown: string): string {
  return markdown
    .split(CODE_SPLIT_RE)
    .map((part, i) => (i % 2 === 1 ? part : part.replace(CITATION_RE, "[\\[$1\\]](#cite-$1)")))
    .join("");
}

export function CitationChip({ n, citation, onClick }: { n: number; citation?: Citation; onClick?: (n: number) => void }) {
  const label = citation ? `${citation.title} — ${citation.domain}` : `Source ${n}`;
  return (
    <button
      type="button"
      onClick={() => onClick?.(n)}
      title={label}
      aria-label={`Citation ${n}: ${label}`}
      className="citation mx-px inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-[5px] border border-line bg-muted px-1 align-middle font-mono text-[10px] font-semibold text-fg-muted no-underline transition-colors hover:border-fg hover:bg-fg hover:text-bg"
    >
      {n}
    </button>
  );
}

export function Markdown({
  content,
  citations = [],
  onCite,
}: {
  content: string;
  citations?: Citation[];
  onCite?: (n: number) => void;
}) {
  const byIndex = new Map(citations.map((c) => [c.index, c]));
  const components: Components = {
    a({ href, children }) {
      if (href?.startsWith("#cite-")) {
        const n = Number(href.slice(6));
        return <CitationChip n={n} citation={byIndex.get(n)} onClick={onCite} />;
      }
      const safe = safeHref(href);
      if (!safe) return <span>{children}</span>;
      return (
        <a href={safe} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    },
    table({ children }) {
      return (
        <div className="overflow-x-auto">
          <table>{children}</table>
        </div>
      );
    },
    img() {
      return null; // reports never need remote images
    },
  };
  return (
    <div className="prose prose-report max-w-none prose-p:leading-7 prose-li:my-1">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linkCitations(content)}
      </ReactMarkdown>
    </div>
  );
}
