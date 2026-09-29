import type {
  Depth,
  Domain,
  Health,
  MemoryMatch,
  ResearchBasic,
  ResearchDetail,
  ResearchList,
  ResearchStatus,
  Source,
  SourceDetail,
} from "./types";

/**
 * Empty by default: the browser calls the same origin and the Next.js route
 * handler in app/api/[...path] forwards to the FastAPI backend (no CORS, only
 * one public port). Set NEXT_PUBLIC_API_URL to call the API directly instead.
 */
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function describeDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String((item as { msg: unknown }).msg) : String(item)))
      .join("; ");
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("The API is unreachable. Is the backend running?", 0);
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      message = describeDetail((await response.json()).detail) ?? message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),

  listResearch: (params: { limit?: number; offset?: number; q?: string; status?: ResearchStatus | "" } = {}) => {
    const search = new URLSearchParams();
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    if (params.q?.trim()) search.set("q", params.q.trim());
    if (params.status) search.set("status", params.status);
    const qs = search.toString();
    return request<ResearchList>(`/api/research${qs ? `?${qs}` : ""}`);
  },

  getResearch: (id: string) => request<ResearchDetail>(`/api/research/${encodeURIComponent(id)}`),

  createResearch: (body: { question: string; depth: Depth; domain: Domain }) =>
    request<ResearchBasic>("/api/research", { method: "POST", body: JSON.stringify(body) }),

  rerun: (id: string) => request<ResearchBasic>(`/api/research/${encodeURIComponent(id)}/rerun`, { method: "POST" }),

  cancel: (id: string) => request<ResearchBasic>(`/api/research/${encodeURIComponent(id)}/cancel`, { method: "POST" }),

  remove: (id: string) => request<void>(`/api/research/${encodeURIComponent(id)}`, { method: "DELETE" }),

  resynthesize: (id: string) =>
    request<ResearchBasic>(`/api/research/${encodeURIComponent(id)}/resynthesize`, { method: "POST" }),

  setSourceExcluded: (researchId: string, sourceId: string, excluded: boolean) =>
    request<Source>(
      `/api/research/${encodeURIComponent(researchId)}/sources/${encodeURIComponent(sourceId)}/${excluded ? "exclude" : "include"}`,
      { method: "POST" },
    ),

  getSource: (researchId: string, sourceId: string) =>
    request<SourceDetail>(`/api/research/${encodeURIComponent(researchId)}/sources/${encodeURIComponent(sourceId)}`),

  searchMemory: (query: string, limit = 12) =>
    request<MemoryMatch[]>("/api/memory/search", { method: "POST", body: JSON.stringify({ query, limit, threshold: 0.2 }) }),

  exportUrl: (id: string, format: "md" | "json") => `${API_BASE}/api/research/${encodeURIComponent(id)}/export?format=${format}`,

  eventsUrl: (id: string, after: number) => `${API_BASE}/api/research/${encodeURIComponent(id)}/events?after=${after}`,
};
