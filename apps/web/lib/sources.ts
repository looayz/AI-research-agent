import type { ResearchDetail, Source } from "./types";

function normalize(url: string): string {
  try {
    const parsed = new URL(url);
    return `${parsed.hostname.replace(/^www\./, "")}${parsed.pathname.replace(/\/$/, "")}${parsed.search}`;
  } catch {
    return url;
  }
}

export interface SourceRef {
  source?: Source;
  /** Citation number in the current report, if the source is part of it. */
  number?: number;
  url: string;
}

/** Resolves claim / contradiction URLs to sources and report citation numbers. */
export class SourceIndex {
  private byUrl = new Map<string, SourceRef>();
  readonly numberById = new Map<string, number>();

  constructor(detail: ResearchDetail | null) {
    if (!detail) return;
    for (const source of detail.sources) this.byUrl.set(normalize(source.url), { source, url: source.url });
    for (const citation of detail.report?.citations ?? []) {
      const key = normalize(citation.url);
      const ref = this.byUrl.get(key) ?? { url: citation.url };
      ref.number = citation.index;
      this.byUrl.set(key, ref);
      if (ref.source) this.numberById.set(ref.source.id, citation.index);
    }
  }

  resolve(url: string): SourceRef {
    return this.byUrl.get(normalize(url)) ?? { url };
  }
}
