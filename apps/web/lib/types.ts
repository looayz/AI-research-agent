export type Depth = "quick" | "standard" | "deep";
export type Domain = "general" | "academic" | "technical" | "market";
export type ResearchStatus =
  | "created"
  | "planning"
  | "searching"
  | "fetching"
  | "analyzing"
  | "verifying"
  | "synthesizing"
  | "completed"
  | "failed"
  | "cancelled";
export type ClaimStatus = "supported" | "partially_supported" | "contradicted" | "insufficient_evidence";

export const TERMINAL_STATUSES: ResearchStatus[] = ["completed", "failed", "cancelled"];

export function isTerminal(status: ResearchStatus | undefined): boolean {
  return !!status && TERMINAL_STATUSES.includes(status);
}

export interface Citation {
  index: number;
  source_id?: string;
  title: string;
  url: string;
  domain: string;
  source_type?: string;
  relevance_score?: number;
  cited?: boolean;
}

export interface Report {
  id: string;
  title: string;
  markdown_content: string;
  executive_summary: string;
  limitations: string[];
  citations: Citation[];
  created_at: string;
}

export interface EvaluationFactors {
  authority?: number;
  query_match?: number;
  search_rank?: number;
  content_depth?: number;
  freshness?: number | null;
  provider?: string;
  memory_similarity?: number;
  memory_from_research?: string;
  [key: string]: unknown;
}

export interface Source {
  id: string;
  research_id: string;
  url: string;
  title: string;
  domain: string;
  published_at: string | null;
  retrieved_at: string;
  source_type: string;
  relevance_score: number;
  is_excluded: boolean;
  evaluation_factors: EvaluationFactors;
  evaluation_notes: string[];
  origin: "search" | "follow_up" | "memory" | string;
  origin_query: string | null;
  fetch_status: "ok" | "provided" | "snippet" | string;
  excerpt: string;
  content_length: number;
}

export interface SourceDetail extends Source {
  content: string;
}

export interface Claim {
  id: string;
  claim_text: string;
  status: ClaimStatus;
  confidence: number;
  supporting_sources: string[];
  contradicting_sources: string[];
  reasoning: string;
  created_at: string;
}

export interface Contradiction {
  id: string;
  topic: string;
  point_a: string;
  source_a_url: string;
  point_b: string;
  source_b_url: string;
  explanation: string;
  created_at: string;
}

export interface SearchQuery {
  id: string;
  sub_question: string | null;
  query: string;
  results_count: number;
  is_follow_up: boolean;
  iteration: number;
}

export interface ResearchPlan {
  objective: string;
  sub_questions: string[];
  search_queries: string[];
  research_scope: string;
  constraints: string[];
}

export interface ResearchEvent {
  id: string;
  seq: number;
  event_type: string;
  agent: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
  created_at: string;
  status?: ResearchStatus | null;
}

export interface ResearchBasic {
  id: string;
  question: string;
  depth: Depth;
  domain: Domain;
  status: ResearchStatus;
  error_message: string | null;
  tokens_used: number;
  llm_calls: number;
  search_calls: number;
  fetch_calls: number;
  runtime_seconds: number;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
}

export interface ResearchSummary extends ResearchBasic {
  report_title: string | null;
  executive_summary: string | null;
  source_count: number;
  claim_count: number;
  contradiction_count: number;
  follow_up_count: number;
}

export interface ResearchList {
  items: ResearchSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ResearchDetail extends ResearchBasic {
  plan: ResearchPlan | null;
  queries: SearchQuery[];
  sources: Source[];
  claims: Claim[];
  contradictions: Contradiction[];
  events: ResearchEvent[];
  report: Report | null;
}

export interface MemoryMatch {
  source: Source;
  similarity_score: number;
  research_question: string | null;
}

export interface Health {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  environment: string;
  mock_mode: boolean;
  demo_mode: boolean;
  database: { status: string; backend: string };
  cache: { status: string; backend: string };
  llm: { provider: string; model: string; configured: boolean };
  search: { providers: string[]; configured: boolean };
  limits: { max_sources: number; max_search_queries: number; max_runtime_seconds: number };
}
