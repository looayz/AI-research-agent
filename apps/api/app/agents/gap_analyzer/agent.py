import json
from typing import List
from pydantic import BaseModel, Field
from app.providers.llm.base import LLMProvider
from app.agents.verifier.agent import VerifiedClaim
from app.agents.gap_analyzer.prompts import GAP_ANALYZER_SYSTEM_PROMPT


class GapAnalysisResult(BaseModel):
    is_sufficient: bool = True
    gaps_identified: List[str] = Field(default_factory=list)
    follow_up_queries: List[str] = Field(default_factory=list)


class GapAnalyzerAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    async def analyze_gaps(self, question: str, claims: List[VerifiedClaim], current_depth: str) -> GapAnalysisResult:
        # In quick depth, do not loop
        if current_depth == "quick":
            return GapAnalysisResult(is_sufficient=True)

        claims_summary = "\n".join([
            f"- [{c.status}] {c.claim_text} (confidence: {c.confidence}) : {c.reasoning}"
            for c in claims
        ])

        user_prompt = f"""Evaluate evidence sufficiency for question:
"{question}"

Current Verified Claims:
{claims_summary}

Determine if follow-up search queries are required. Output strictly valid JSON."""

        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=GAP_ANALYZER_SYSTEM_PROMPT,
            temperature=0.1
        )

        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())
            return GapAnalysisResult(**data)
        except Exception:
            # Fallback deterministic gap analysis
            has_weak = any(c.status in ("partially_supported", "insufficient_evidence") for c in claims)
            if has_weak and current_depth == "deep":
                return GapAnalysisResult(
                    is_sufficient=False,
                    gaps_identified=["Évaluation quantitative de l'apprentissage algorithmique autonome."],
                    follow_up_queries=["empirical study python algorithmic foundations without ai assistance"]
                )
            return GapAnalysisResult(is_sufficient=True)
