"use client";

import { useState, useRef, useEffect } from "react";
import {
  Search,
  Compass,
  BookOpen,
  History,
  Settings,
  ArrowRight,
  ShieldCheck,
  FileCheck,
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  XCircle,
  FileText,
  Ban,
  Activity,
  Download,
  RotateCcw,
  Trash2,
  Sparkles,
  GitBranch,
  GraduationCap,
  Cpu,
  TrendingUp,
  Globe,
  Database,
  Layers,
  ChevronRight
} from "lucide-react";

interface Citation {
  index: number;
  title: string;
  url: string;
  domain: string;
  source_type?: string;
  relevance_score?: number;
}

interface Report {
  title: string;
  markdown_content: string;
  executive_summary: string;
  limitations: string[];
  citations: Citation[];
}

interface Source {
  id: string;
  url: string;
  title: string;
  domain: string;
  content?: string;
  relevance_score: number;
  source_type: string;
  is_excluded: boolean;
}

interface Claim {
  id: string;
  claim_text: string;
  status: "supported" | "partially_supported" | "contradicted" | "insufficient_evidence";
  confidence: number;
  supporting_sources: string[];
  contradicting_sources: string[];
  reasoning: string;
}

interface Contradiction {
  id: string;
  topic: string;
  point_a: string;
  source_a_url: string;
  point_b: string;
  source_b_url: string;
  explanation: string;
}

interface SearchQuery {
  id: string;
  query: string;
  is_follow_up: boolean;
}

interface ResearchEvent {
  id: string;
  event_type: string;
  agent: string;
  data: any;
  created_at: string;
}

interface ResearchDetail {
  id: string;
  question: string;
  depth: "quick" | "standard" | "deep";
  domain: "general" | "academic" | "technical" | "market";
  status: string;
  runtime_seconds: number;
  llm_calls: number;
  search_calls: number;
  queries: SearchQuery[];
  sources: Source[];
  claims: Claim[];
  contradictions: Contradiction[];
  report?: Report;
}

interface MemoryMatch {
  source: Source;
  similarity_score: number;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [depth, setDepth] = useState<"quick" | "standard" | "deep">("deep");
  const [domain, setDomain] = useState<"general" | "academic" | "technical" | "market">("academic");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<string>("idle");
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [research, setResearch] = useState<ResearchDetail | null>(null);
  const [historyList, setHistoryList] = useState<ResearchDetail[]>([]);
  const [activeView, setActiveView] = useState<"dashboard" | "history" | "memory">("dashboard");
  const [activeTab, setActiveTab] = useState<"report" | "claims" | "contradictions" | "sources" | "timeline">("timeline");
  
  // Semantic Memory Search
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryResults, setMemoryResults] = useState<MemoryMatch[]>([]);
  const [memoryLoading, setMemoryLoading] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/research");
      if (res.ok) {
        const data = await res.json();
        setHistoryList(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const searchSemanticMemory = async () => {
    if (!memoryQuery.trim()) return;
    setMemoryLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/memory/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: memoryQuery, threshold: 0.45, limit: 8 }),
      });
      if (res.ok) {
        const data = await res.json();
        setMemoryResults(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setMemoryLoading(false);
    }
  };

  const startResearch = async (customQuery?: string) => {
    const q = customQuery || question;
    if (!q.trim()) return;
    setLoading(true);
    setResearch(null);
    setEvents([]);
    setCurrentStep("planning");
    setActiveTab("timeline");
    setActiveView("dashboard");

    try {
      const res = await fetch("http://localhost:8000/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, depth, domain }),
      });
      const data = await res.json();
      const researchId = data.id;

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const eventSource = new EventSource(`http://localhost:8000/api/research/${researchId}/events`);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = async (e) => {
        const ev: ResearchEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, ev]);

        if (ev.event_type === "planner.started") setCurrentStep("planning");
        if (ev.event_type === "search.started") setCurrentStep("searching");
        if (ev.event_type === "verifier.started") setCurrentStep("verifying");
        if (ev.event_type === "gap_analyzer.started") setCurrentStep("gap_analysis");
        if (ev.event_type === "follow_up.started") setCurrentStep("deep_search");
        if (ev.event_type === "synthesizer.started") setCurrentStep("synthesizing");

        if (ev.event_type === "research.completed" || ev.event_type === "research.failed") {
          eventSource.close();
          setCurrentStep(ev.event_type === "research.completed" ? "completed" : "failed");
          setLoading(false);

          const check = await fetch(`http://localhost:8000/api/research/${researchId}`);
          const current = await check.json();
          setResearch(current);
          setActiveTab("report");
          fetchHistory();
        }
      };

      eventSource.onerror = async () => {
        eventSource.close();
        const check = await fetch(`http://localhost:8000/api/research/${researchId}`);
        const current = await check.json();
        setResearch(current);
        setLoading(false);
        fetchHistory();
      };
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  const rerunResearch = async (id: string) => {
    try {
      setLoading(true);
      const res = await fetch(`http://localhost:8000/api/research/${id}/rerun`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setQuestion(data.question);
        setDomain(data.domain || "general");
        setDepth(data.depth || "standard");
        startResearch(data.question);
      }
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  const deleteResearch = async (id: string) => {
    try {
      await fetch(`http://localhost:8000/api/research/${id}`, { method: "DELETE" });
      setHistoryList((prev) => prev.filter((item) => item.id !== id));
      if (research?.id === id) {
        setResearch(null);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const downloadMarkdown = () => {
    if (!research?.report) return;
    const blob = new Blob([research.report.markdown_content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-report-${research.id.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const excludeSource = async (sourceId: string) => {
    if (!research) return;
    try {
      await fetch(`http://localhost:8000/api/research/${research.id}/sources/${sourceId}/exclude`, {
        method: "POST",
      });
      setResearch({
        ...research,
        sources: research.sources.map((s) => (s.id === sourceId ? { ...s, is_excluded: true } : s)),
      });
    } catch (e) {
      console.error(e);
    }
  };

  const getStatusBadge = (status: Claim["status"]) => {
    switch (status) {
      case "supported":
        return (
          <span className="flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-zinc-900 text-white font-medium border border-zinc-900">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Supported
          </span>
        );
      case "partially_supported":
        return (
          <span className="flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-zinc-100 text-zinc-800 font-medium border border-zinc-300">
            <HelpCircle className="w-3 h-3 text-zinc-600" /> Partial
          </span>
        );
      case "contradicted":
        return (
          <span className="flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-zinc-900 text-rose-300 font-medium border border-rose-900/50">
            <XCircle className="w-3 h-3 text-rose-400" /> Contradicted
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1.5 text-xs px-2.5 py-0.5 rounded-full bg-zinc-100 text-zinc-700 font-medium border border-zinc-200">
            <AlertTriangle className="w-3 h-3 text-zinc-500" /> Insufficient
          </span>
        );
    }
  };

  return (
    <div className="flex h-screen bg-[#f7f7f5] text-[#121316] overflow-hidden antialiased">
      {/* Sleek Dark Minimal Sidebar */}
      <aside className="w-64 bg-[#0e0f11] text-zinc-300 border-r border-[#1c1d21] flex flex-col justify-between p-5 shrink-0 select-none">
        <div className="space-y-7">
          <div className="flex items-center gap-3 px-1">
            <div className="w-9 h-9 rounded-xl bg-white text-black flex items-center justify-center font-bold tracking-tighter text-base shadow-sm">
              AI
            </div>
            <div>
              <h1 className="font-semibold text-sm tracking-tight text-white flex items-center gap-1.5">
                Research Agent
              </h1>
              <span className="text-[10px] text-zinc-400 font-mono tracking-wider uppercase flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-white inline-block"></span> v2.4 Monochrome
              </span>
            </div>
          </div>

          <nav className="space-y-1.5">
            <button
              onClick={() => setActiveView("dashboard")}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
                activeView === "dashboard"
                  ? "bg-white text-black shadow-sm"
                  : "text-zinc-400 hover:text-white hover:bg-[#1a1b1f]"
              }`}
            >
              <div className="flex items-center gap-3">
                <Compass className="w-4 h-4" />
                <span>Console</span>
              </div>
              {activeView === "dashboard" && <ChevronRight className="w-3.5 h-3.5 text-black" />}
            </button>
            <button
              onClick={() => setActiveView("history")}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
                activeView === "history"
                  ? "bg-white text-black shadow-sm"
                  : "text-zinc-400 hover:text-white hover:bg-[#1a1b1f]"
              }`}
            >
              <div className="flex items-center gap-3">
                <History className="w-4 h-4" />
                <span>Investigations</span>
              </div>
              <span
                className={`text-[11px] font-mono px-2 py-0.5 rounded-md ${
                  activeView === "history" ? "bg-zinc-200 text-black" : "bg-[#1c1d21] text-zinc-400"
                }`}
              >
                {historyList.length}
              </span>
            </button>
            <button
              onClick={() => setActiveView("memory")}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
                activeView === "memory"
                  ? "bg-white text-black shadow-sm"
                  : "text-zinc-400 hover:text-white hover:bg-[#1a1b1f]"
              }`}
            >
              <div className="flex items-center gap-3">
                <Database className="w-4 h-4" />
                <span>Semantic Memory</span>
              </div>
              {activeView === "memory" && <ChevronRight className="w-3.5 h-3.5 text-black" />}
            </button>
          </nav>
        </div>

        <div className="border-t border-[#1c1d21] pt-4 space-y-3">
          <div className="flex items-center justify-between text-xs text-zinc-500 font-mono">
            <span>LLM / SEARCH</span>
            <span className="text-zinc-300">HYBRID MOCK</span>
          </div>
          <div className="flex items-center justify-between text-xs text-zinc-500 font-mono">
            <span>STORAGE</span>
            <span className="text-zinc-300">SQLITE + MEMORY</span>
          </div>
        </div>
      </aside>

      {/* Main App Canvas */}
      <main className="flex-1 flex flex-col overflow-y-auto">
        {/* Subtle Off-white Header */}
        <header className="h-16 border-b border-[#e5e5e0] px-8 flex items-center justify-between bg-white/70 backdrop-blur-md shrink-0 sticky top-0 z-20">
          <div className="flex items-center gap-3 text-xs font-mono text-zinc-600">
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                loading ? "bg-black animate-ping" : "bg-zinc-900"
              }`}
            ></span>
            <span className="font-semibold text-black tracking-wider uppercase">DOMAIN: {domain}</span>
            <span className="text-zinc-300">/</span>
            <span className="uppercase text-zinc-600">DEPTH: {depth}</span>
            <span className="text-zinc-300">/</span>
            <span className="text-zinc-500">
              {loading ? `STEP: [${currentStep.toUpperCase()}]` : "STATUS: IDLE"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Domain Selector */}
            <div className="flex items-center bg-[#f0f0ec] p-1 rounded-xl border border-[#e4e4df] text-xs">
              <button
                onClick={() => setDomain("general")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition ${
                  domain === "general"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                <Globe className="w-3.5 h-3.5" />
                <span>General</span>
              </button>
              <button
                onClick={() => setDomain("academic")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition ${
                  domain === "academic"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                <GraduationCap className="w-3.5 h-3.5" />
                <span>Academic</span>
              </button>
              <button
                onClick={() => setDomain("technical")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition ${
                  domain === "technical"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                <Cpu className="w-3.5 h-3.5" />
                <span>Technical</span>
              </button>
              <button
                onClick={() => setDomain("market")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition ${
                  domain === "market"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Market</span>
              </button>
            </div>

            {/* Depth Selector */}
            <div className="flex items-center bg-[#f0f0ec] p-1 rounded-xl border border-[#e4e4df] text-xs">
              <button
                onClick={() => setDepth("quick")}
                className={`px-3 py-1 rounded-lg transition ${
                  depth === "quick"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                Quick
              </button>
              <button
                onClick={() => setDepth("standard")}
                className={`px-3 py-1 rounded-lg transition ${
                  depth === "standard"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                Standard
              </button>
              <button
                onClick={() => setDepth("deep")}
                className={`px-3 py-1 rounded-lg transition ${
                  depth === "deep"
                    ? "bg-white text-black font-semibold shadow-sm"
                    : "text-zinc-600 hover:text-black"
                }`}
              >
                Deep Loop
              </button>
            </div>
          </div>
        </header>

        {/* View 1: History Screen */}
        {activeView === "history" && (
          <div className="p-10 max-w-5xl mx-auto w-full space-y-6">
            <div className="border-b border-[#e4e4e0] pb-5">
              <h2 className="text-3xl font-bold tracking-tight text-black">Investigations History</h2>
              <p className="text-zinc-500 text-sm mt-1">
                Previous investigations archived locally with claims, extracted sources, and semantic memory tags.
              </p>
            </div>

            <div className="space-y-3">
              {historyList.map((item) => (
                <div
                  key={item.id}
                  className="p-5 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm hover:border-black/30 transition flex items-center justify-between"
                >
                  <div className="space-y-1.5 max-w-2xl">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
                        #{item.id.slice(0, 8)}
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-md bg-zinc-100 text-zinc-700 font-semibold border border-zinc-200">
                        {item.domain || "general"}
                      </span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-md bg-zinc-900 text-white font-semibold">
                        {item.depth || "standard"}
                      </span>
                    </div>
                    <h4 className="font-semibold text-base text-zinc-900 line-clamp-1">{item.question}</h4>
                    <div className="flex items-center gap-3 text-xs text-zinc-500 pt-1 font-mono">
                      <span>Status: {item.status}</span>
                      <span>•</span>
                      <span>Runtime: {item.runtime_seconds}s</span>
                      <span>•</span>
                      <span>Sources: {item.sources?.length || 0}</span>
                      <span>•</span>
                      <span>Follow-up: {item.queries?.filter((q) => q.is_follow_up).length || 0}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setResearch(item);
                        setActiveView("dashboard");
                        setActiveTab("report");
                      }}
                      className="px-3.5 py-2 rounded-xl bg-black text-white text-xs font-semibold hover:bg-zinc-800 transition"
                    >
                      Inspect Report
                    </button>
                    <button
                      onClick={() => rerunResearch(item.id)}
                      className="p-2 rounded-xl bg-zinc-100 text-zinc-700 border border-zinc-200 hover:text-black hover:bg-zinc-200 transition"
                      title="Rerun"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => deleteResearch(item.id)}
                      className="p-2 rounded-xl bg-zinc-100 text-zinc-500 border border-zinc-200 hover:text-rose-600 hover:bg-rose-50 hover:border-rose-200 transition"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
              {historyList.length === 0 && (
                <div className="text-zinc-400 text-center py-16 bg-white rounded-2xl border border-dashed border-[#e4e4e0]">
                  No previous investigations yet.
                </div>
              )}
            </div>
          </div>
        )}

        {/* View 2: Semantic Memory Search */}
        {activeView === "memory" && (
          <div className="p-10 max-w-5xl mx-auto w-full space-y-6">
            <div className="border-b border-[#e4e4e0] pb-5">
              <h2 className="text-3xl font-bold tracking-tight text-black">Semantic Memory Recall</h2>
              <p className="text-zinc-500 text-sm mt-1">
                Vector similarity search (128-dimensional embeddings) across past collected evidence and papers.
              </p>
            </div>

            <div className="relative flex items-center">
              <Search className="absolute left-4 w-5 h-5 text-zinc-400" />
              <input
                type="text"
                value={memoryQuery}
                onChange={(e) => setMemoryQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !memoryLoading && searchSemanticMemory()}
                placeholder="Query semantic memory (e.g. 'pedagogy and python feedback loop')..."
                className="w-full bg-white border border-[#e4e4e0] rounded-2xl pl-12 pr-36 py-4 text-sm text-black placeholder-zinc-400 focus:outline-none focus:border-black focus:ring-1 focus:ring-black shadow-sm transition"
              />
              <button
                onClick={searchSemanticMemory}
                disabled={memoryLoading || !memoryQuery.trim()}
                className="absolute right-3 px-4 py-2 bg-black hover:bg-zinc-800 disabled:opacity-40 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition"
              >
                {memoryLoading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <span>Query Memory</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {memoryResults.map(({ source, similarity_score }) => (
                <div
                  key={source.id}
                  className="p-5 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm space-y-3 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-zinc-500">{source.domain}</span>
                      <span className="font-mono bg-zinc-100 text-zinc-800 font-semibold px-2 py-0.5 rounded-md border border-zinc-200">
                        Score: {Math.round(similarity_score * 100)}%
                      </span>
                    </div>
                    <h4 className="font-semibold text-sm text-black">{source.title}</h4>
                    <p className="text-xs text-zinc-600 line-clamp-3 leading-relaxed">{source.content}</p>
                  </div>
                  <div className="pt-3 border-t border-[#f0f0ec]">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-black font-medium hover:underline flex items-center gap-1.5"
                    >
                      <span>Visit original citation</span>
                      <ExternalLink className="w-3 h-3 text-zinc-400" />
                    </a>
                  </div>
                </div>
              ))}
              {memoryResults.length === 0 && !memoryLoading && (
                <div className="col-span-2 text-zinc-400 text-center py-16 bg-white rounded-2xl border border-dashed border-[#e4e4e0]">
                  Type a prompt above to search indexed semantic memory.
                </div>
              )}
            </div>
          </div>
        )}

        {/* View 3: Dashboard Console */}
        {activeView === "dashboard" && (
          <div className="p-10 max-w-5xl mx-auto w-full space-y-8">
            {/* Header / Intro */}
            <div className="flex items-end justify-between border-b border-[#e4e4e0] pb-6">
              <div>
                <span className="text-xs font-mono uppercase tracking-widest text-zinc-400">
                  AUTONOMOUS MULTI-AGENT ENGINE
                </span>
                <h2 className="text-3xl font-bold tracking-tight text-black mt-1">Deep Research Lab</h2>
                <p className="text-zinc-500 text-sm mt-1">
                  Synthesize high-credibility reports, cross-examine claims, and detect contradictions.
                </p>
              </div>
            </div>

            {/* Premium Black & White Search Console */}
            <div className="relative">
              <div className="relative flex items-center shadow-sm">
                <Search className="absolute left-5 w-5 h-5 text-zinc-400" />
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !loading && startResearch()}
                  placeholder={`Explore any topic in ${domain} mode (e.g. 'Compare post-quantum cryptography algorithms and NIST standardization')...`}
                  className="w-full bg-white border border-[#e4e4e0] rounded-2xl pl-14 pr-44 py-5 text-sm text-black placeholder-zinc-400 focus:outline-none focus:border-black focus:ring-1 focus:ring-black transition"
                />
                <button
                  onClick={() => startResearch()}
                  disabled={loading || !question.trim()}
                  className="absolute right-3.5 px-5 py-2.5 bg-black hover:bg-zinc-800 disabled:opacity-40 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Investigating...</span>
                    </>
                  ) : (
                    <>
                      <span>Start Research</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Stepper Pipeline */}
            {(loading || research) && (
              <div className="p-3 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm grid grid-cols-5 gap-2">
                <div
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition ${
                    currentStep === "planning"
                      ? "border-black bg-black text-white font-medium shadow-sm"
                      : "border-transparent bg-zinc-50 text-zinc-500"
                  }`}
                >
                  <Compass className="w-3.5 h-3.5 shrink-0" />
                  <div className="text-[11px] truncate">1. Planning</div>
                </div>
                <div
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition ${
                    currentStep === "searching"
                      ? "border-black bg-black text-white font-medium shadow-sm"
                      : "border-transparent bg-zinc-50 text-zinc-500"
                  }`}
                >
                  <Search className="w-3.5 h-3.5 shrink-0" />
                  <div className="text-[11px] truncate">2. Retrieval</div>
                </div>
                <div
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition ${
                    currentStep === "verifying"
                      ? "border-black bg-black text-white font-medium shadow-sm"
                      : "border-transparent bg-zinc-50 text-zinc-500"
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                  <div className="text-[11px] truncate">3. Verification</div>
                </div>
                <div
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition ${
                    currentStep === "gap_analysis" || currentStep === "deep_search"
                      ? "border-black bg-black text-white font-medium shadow-sm"
                      : "border-transparent bg-zinc-50 text-zinc-500"
                  }`}
                >
                  <GitBranch className="w-3.5 h-3.5 shrink-0" />
                  <div className="text-[11px] truncate">4. Gap Loop</div>
                </div>
                <div
                  className={`flex items-center gap-2 p-2.5 rounded-xl border transition ${
                    currentStep === "synthesizing" || currentStep === "completed"
                      ? "border-black bg-black text-white font-medium shadow-sm"
                      : "border-transparent bg-zinc-50 text-zinc-500"
                  }`}
                >
                  <FileCheck className="w-3.5 h-3.5 shrink-0" />
                  <div className="text-[11px] truncate">5. Synthesis</div>
                </div>
              </div>
            )}

            {/* Results Navigation Tabs */}
            {(events.length > 0 || research) && (
              <div className="space-y-6">
                <div className="flex items-center justify-between border-b border-[#e4e4e0] pb-2">
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => setActiveTab("timeline")}
                      className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-medium transition ${
                        activeTab === "timeline"
                          ? "bg-black text-white shadow-sm"
                          : "text-zinc-600 hover:text-black hover:bg-zinc-100"
                      }`}
                    >
                      <Activity className="w-3.5 h-3.5" />
                      <span>Telemetry ({events.length})</span>
                    </button>
                    {research?.report && (
                      <button
                        onClick={() => setActiveTab("report")}
                        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-medium transition ${
                          activeTab === "report"
                            ? "bg-black text-white shadow-sm"
                            : "text-zinc-600 hover:text-black hover:bg-zinc-100"
                        }`}
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Synthesis</span>
                      </button>
                    )}
                    {research && (
                      <>
                        <button
                          onClick={() => setActiveTab("claims")}
                          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-medium transition ${
                            activeTab === "claims"
                              ? "bg-black text-white shadow-sm"
                              : "text-zinc-600 hover:text-black hover:bg-zinc-100"
                          }`}
                        >
                          <ShieldCheck className="w-3.5 h-3.5" />
                          <span>Claims ({research.claims.length})</span>
                        </button>
                        <button
                          onClick={() => setActiveTab("contradictions")}
                          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-medium transition ${
                            activeTab === "contradictions"
                              ? "bg-black text-white shadow-sm"
                              : "text-zinc-600 hover:text-black hover:bg-zinc-100"
                          }`}
                        >
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>Contradictions ({research.contradictions.length})</span>
                        </button>
                        <button
                          onClick={() => setActiveTab("sources")}
                          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-medium transition ${
                            activeTab === "sources"
                              ? "bg-black text-white shadow-sm"
                              : "text-zinc-600 hover:text-black hover:bg-zinc-100"
                          }`}
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>Sources ({research.sources.length})</span>
                        </button>
                      </>
                    )}
                  </div>

                  {research?.report && (
                    <button
                      onClick={downloadMarkdown}
                      className="px-3.5 py-1.5 rounded-xl bg-white border border-[#e4e4e0] text-black hover:bg-zinc-100 text-xs font-medium flex items-center gap-2 transition shadow-sm"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Export .md</span>
                    </button>
                  )}
                </div>

                {/* Tab: Real-Time SSE Timeline */}
                {activeTab === "timeline" && (
                  <div className="p-6 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm space-y-4">
                    <div className="flex items-center justify-between border-b border-[#f0f0ec] pb-3">
                      <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
                        Agent Multi-Thread Feed
                      </span>
                      <span className="text-xs font-mono text-zinc-400">Streaming SSE Connection</span>
                    </div>
                    <div className="space-y-2.5 font-mono text-xs">
                      {events.map((ev, idx) => (
                        <div
                          key={ev.id || idx}
                          className="p-3 rounded-xl bg-[#fafafa] border border-[#ebebe6] flex items-start gap-3"
                        >
                          <span className="px-1.5 py-0.5 rounded bg-black text-white text-[10px] font-bold">
                            {ev.agent.toUpperCase()}
                          </span>
                          <div className="flex-1 space-y-0.5">
                            <div className="text-zinc-900 font-semibold">{ev.event_type}</div>
                            <div className="text-zinc-500 text-[11px] truncate">
                              {JSON.stringify(ev.data)}
                            </div>
                          </div>
                        </div>
                      ))}
                      {events.length === 0 && (
                        <div className="text-zinc-400 text-center py-8">
                          Launch an investigation above to observe real-time agent coordination.
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Tab: Final Report */}
                {activeTab === "report" && research?.report && (
                  <div className="space-y-6">
                    <div className="p-8 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm space-y-6">
                      <div className="flex items-start justify-between border-b border-[#f0f0ec] pb-5">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-mono uppercase bg-zinc-100 text-zinc-800 border border-zinc-200 px-2 py-0.5 rounded-md font-semibold">
                              Profile: {research.domain}
                            </span>
                            <span className="text-[10px] font-mono uppercase bg-zinc-900 text-white px-2 py-0.5 rounded-md font-semibold">
                              Depth: {research.depth}
                            </span>
                          </div>
                          <h3 className="text-2xl font-bold text-black mt-2">{research.report.title}</h3>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs bg-zinc-100 text-zinc-800 border border-zinc-200 px-3 py-1 rounded-full flex items-center gap-1 font-mono">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Status: {research.status}
                          </span>
                          <span className="text-xs bg-zinc-100 text-zinc-800 border border-zinc-200 px-3 py-1 rounded-full font-mono">
                            Runtime: {research.runtime_seconds}s
                          </span>
                        </div>
                      </div>

                      <div className="prose max-w-none text-zinc-800 text-sm leading-relaxed whitespace-pre-wrap">
                        {research.report.markdown_content}
                      </div>
                    </div>

                    {/* Citations Registry */}
                    <div className="p-6 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm space-y-3">
                      <h4 className="text-xs font-semibold tracking-wider uppercase text-zinc-400 font-mono">
                        Documented Citations & Sources Registry
                      </h4>
                      <div className="space-y-2">
                        {research.report.citations.map((c) => (
                          <div
                            key={c.index}
                            className="flex items-center justify-between p-3.5 rounded-xl bg-[#fafafa] border border-[#ebebe6] text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-black bg-zinc-200 px-1.5 py-0.5 rounded">
                                [{c.index}]
                              </span>
                              <span className="text-zinc-900 font-medium">{c.title}</span>
                              <span className="text-zinc-400">({c.domain})</span>
                              {c.source_type && (
                                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-700">
                                  {c.source_type}
                                </span>
                              )}
                            </div>
                            <a
                              href={c.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-black font-semibold hover:underline flex items-center gap-1 shrink-0 ml-4"
                            >
                              <span>Direct Link</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Tab: Claims */}
                {activeTab === "claims" && research && (
                  <div className="space-y-3">
                    {research.claims.map((claim) => (
                      <div
                        key={claim.id}
                        className="p-5 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm space-y-3"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {getStatusBadge(claim.status)}
                            <span className="text-xs font-mono text-zinc-500">
                              Confidence: {Math.round(claim.confidence * 100)}%
                            </span>
                          </div>
                        </div>
                        <p className="text-sm font-semibold text-zinc-900">{claim.claim_text}</p>
                        <div className="text-xs text-zinc-600 bg-[#fafafa] p-3.5 rounded-xl border border-[#ebebe6]">
                          <span className="font-bold text-black">Reasoning: </span>
                          {claim.reasoning}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Tab: Contradictions */}
                {activeTab === "contradictions" && research && (
                  <div className="space-y-4">
                    {research.contradictions.map((c) => (
                      <div
                        key={c.id}
                        className="p-6 rounded-2xl bg-white border border-[#e4e4e0] shadow-sm space-y-4"
                      >
                        <div className="flex items-center gap-2 text-black font-semibold text-sm">
                          <AlertTriangle className="w-4 h-4 text-zinc-700" />
                          <span>Topic Conflict: {c.topic}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="p-4 rounded-xl bg-[#fafafa] border border-[#ebebe6] space-y-2">
                            <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider font-semibold">
                              Evidence A
                            </span>
                            <p className="text-xs text-zinc-800 leading-relaxed">{c.point_a}</p>
                          </div>
                          <div className="p-4 rounded-xl bg-[#fafafa] border border-[#ebebe6] space-y-2">
                            <span className="text-xs font-mono text-zinc-500 uppercase tracking-wider font-semibold">
                              Evidence B
                            </span>
                            <p className="text-xs text-zinc-800 leading-relaxed">{c.point_b}</p>
                          </div>
                        </div>
                        <div className="p-3.5 rounded-xl bg-zinc-100 border border-zinc-200 text-xs text-zinc-900">
                          <span className="font-bold text-black">Synthesis Verdict: </span>
                          {c.explanation}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Tab: Sources */}
                {activeTab === "sources" && research && (
                  <div className="grid grid-cols-2 gap-4">
                    {research.sources.map((src, i) => (
                      <div
                        key={src.id}
                        className={`p-5 rounded-2xl bg-white border shadow-sm ${
                          src.is_excluded ? "border-rose-300 opacity-50 bg-rose-50/20" : "border-[#e4e4e0]"
                        } flex flex-col justify-between space-y-3`}
                      >
                        <div>
                          <div className="flex items-center justify-between text-xs text-zinc-500">
                            <span className="font-mono font-medium">
                              [{i + 1}] {src.domain}
                            </span>
                            <span className="capitalize bg-zinc-100 px-2 py-0.5 rounded text-zinc-700 text-[10px] font-mono">
                              {src.source_type}
                            </span>
                          </div>
                          <h5 className="font-semibold text-sm text-black mt-2">{src.title}</h5>
                        </div>
                        <div className="flex items-center justify-between pt-3 border-t border-[#f0f0ec]">
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-black font-medium hover:underline flex items-center gap-1"
                          >
                            <span>Inspect Source</span>
                            <ExternalLink className="w-3 h-3 text-zinc-400" />
                          </a>
                          {!src.is_excluded ? (
                            <button
                              onClick={() => excludeSource(src.id)}
                              className="text-[11px] text-zinc-500 hover:text-rose-600 flex items-center gap-1 font-mono transition"
                            >
                              <Ban className="w-3 h-3" />
                              <span>Exclude</span>
                            </button>
                          ) : (
                            <span className="text-[11px] text-rose-600 font-mono">Excluded</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
