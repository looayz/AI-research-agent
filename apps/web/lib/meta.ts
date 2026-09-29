import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Cpu,
  GraduationCap,
  Globe,
  HelpCircle,
  TrendingUp,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { ClaimStatus, Depth, Domain, ResearchStatus } from "./types";

export const DOMAINS: Record<Domain, { label: string; icon: LucideIcon; hint: string }> = {
  general: { label: "General", icon: Globe, hint: "Reference works, reputable press, official statistics" },
  academic: { label: "Academic", icon: GraduationCap, hint: "Peer-reviewed studies, meta-analyses, preprints" },
  technical: { label: "Technical", icon: Cpu, hint: "Docs, specs & RFCs, repositories, benchmarks" },
  market: { label: "Market", icon: TrendingUp, hint: "Market sizing, filings, industry reports" },
};

export const DEPTHS: Record<Depth, { label: string; hint: string }> = {
  quick: { label: "Quick", hint: "One search pass, no follow-up" },
  standard: { label: "Standard", hint: "One gap-analysis round with follow-up searches" },
  deep: { label: "Deep", hint: "Up to three gap-analysis rounds, re-verified each time" },
};

export type Tone = "neutral" | "success" | "warning" | "danger" | "info";

export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-fg-muted",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

export const TONE_BADGE: Record<Tone, string> = {
  neutral: "bg-muted text-fg-muted border-line",
  success: "bg-success/10 text-success border-success/25",
  warning: "bg-warning/10 text-warning border-warning/25",
  danger: "bg-danger/10 text-danger border-danger/25",
  info: "bg-info/10 text-info border-info/25",
};

export const TONE_BAR: Record<Tone, string> = {
  neutral: "bg-fg-subtle",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
};

export const CLAIM_STATUS: Record<ClaimStatus, { label: string; short: string; tone: Tone; icon: LucideIcon }> = {
  supported: { label: "Supported", short: "Supported", tone: "success", icon: CheckCircle2 },
  partially_supported: { label: "Partially supported", short: "Partial", tone: "warning", icon: HelpCircle },
  contradicted: { label: "Contradicted", short: "Contradicted", tone: "danger", icon: XCircle },
  insufficient_evidence: { label: "Insufficient evidence", short: "Insufficient", tone: "neutral", icon: CircleDashed },
};

export const CLAIM_ORDER: ClaimStatus[] = ["supported", "partially_supported", "contradicted", "insufficient_evidence"];

export const STATUS_META: Record<ResearchStatus, { label: string; tone: Tone }> = {
  created: { label: "Queued", tone: "info" },
  planning: { label: "Planning", tone: "info" },
  searching: { label: "Searching", tone: "info" },
  fetching: { label: "Reading sources", tone: "info" },
  analyzing: { label: "Analyzing gaps", tone: "info" },
  verifying: { label: "Verifying", tone: "info" },
  synthesizing: { label: "Writing report", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "warning" },
};

export const WarningIcon = AlertTriangle;
