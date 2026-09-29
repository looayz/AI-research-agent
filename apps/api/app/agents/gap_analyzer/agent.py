import re
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import generate_structured
from app.agents.gap_analyzer.prompts import GAP_ANALYZER_SYSTEM_PROMPT, GAP_ANALYZER_USER_PROMPT
from app.agents.verifier.agent import DetectedContradiction, VerifiedClaim
from app.core.text import clip
from app.providers.llm.base import LLMProvider


class GapAnalysisResult(BaseModel):
    is_sufficient: bool = True
    gaps_identified: list[str] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)


def _bullets(items: list[str], empty: str = "- (none)") -> str:
    return "\n".join(f"- {item}" for item in items) if items else empty


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


class GapAnalyzerAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    @staticmethod
    def build_prompt(
        question: str,
        sub_questions: list[str],
        claims: list[VerifiedClaim],
        contradictions: list[DetectedContradiction],
        previous_queries: list[str],
        round_number: int,
        max_rounds: int,
        max_queries: int,
    ) -> str:
        claim_lines = [
            f"[{c.status.value}, confidence {c.confidence:.2f}] {c.claim_text} ({len(c.supporting_sources)} supporting source(s))"
            for c in claims
        ]
        contradiction_lines = [f"{c.topic}: {clip(c.point_a, 120)} / {clip(c.point_b, 120)}" for c in contradictions]
        return GAP_ANALYZER_USER_PROMPT.format(
            question=question,
            sub_questions=_bullets(sub_questions),
            claims=_bullets(claim_lines),
            contradictions=_bullets(contradiction_lines),
            queries=_bullets(previous_queries),
            round=round_number,
            max_rounds=max_rounds,
            max_queries=max_queries,
        )

    @staticmethod
    def _normalize(data: Any, previous_queries: list[str], max_queries: int) -> GapAnalysisResult:
        if not isinstance(data, dict):
            raise ValueError("gap analysis is not a JSON object")
        already = {q.strip().lower() for q in previous_queries}
        queries: list[str] = []
        for raw in data.get("follow_up_queries") or []:
            query = clip(re.sub(r"\s+", " ", re.sub(r"[\"“”«»?]", " ", str(raw))).strip(), 300)
            if query and query.lower() not in already:
                already.add(query.lower())
                queries.append(query)
        gaps = [str(g).strip() for g in data.get("gaps_identified") or [] if str(g).strip()]
        sufficient = _as_bool(data.get("is_sufficient", not queries))
        return GapAnalysisResult(
            is_sufficient=sufficient or not queries,
            gaps_identified=gaps[:6],
            follow_up_queries=[] if sufficient else queries[:max_queries],
        )

    async def analyze_gaps(
        self,
        question: str,
        claims: list[VerifiedClaim],
        *,
        contradictions: list[DetectedContradiction] | None = None,
        sub_questions: list[str] | None = None,
        previous_queries: list[str] | None = None,
        round_number: int = 1,
        max_rounds: int = 1,
        max_queries: int = 3,
    ) -> GapAnalysisResult:
        previous = previous_queries or []
        return await generate_structured(
            self.llm,
            prompt=self.build_prompt(
                question, sub_questions or [], claims, contradictions or [], previous, round_number, max_rounds, max_queries
            ),
            system_prompt=GAP_ANALYZER_SYSTEM_PROMPT,
            parse=lambda data: self._normalize(data, previous, max_queries),
            temperature=0.2,
            max_tokens=1200,
        )
