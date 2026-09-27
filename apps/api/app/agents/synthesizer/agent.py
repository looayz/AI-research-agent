from typing import List, Dict, Any
from app.providers.llm.base import LLMProvider
from app.agents.researcher.agent import CollectedSource
from app.agents.synthesizer.prompts import SYNTHESIZER_SYSTEM_PROMPT
from pydantic import BaseModel


class SynthesizedReport(BaseModel):
    title: str
    markdown_content: str
    executive_summary: str
    limitations: List[str]
    citations: List[Dict[str, Any]]


class SynthesizerAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    async def generate_report(self, question: str, sources: List[CollectedSource], domain: str = "general") -> SynthesizedReport:
        sources_summary = "\n\n".join([
            f"[{idx + 1}] Title: {s.title}\nDomain: {s.domain} ({s.source_type})\nURL: {s.url}\nExcerpt: {s.content[:350]}..."
            for idx, s in enumerate(sources)
        ])

        user_prompt = f"""Synthesize a complete, rigorous research report in the [{domain.upper()}] domain for question:
"{question}"

Using the following verified sources:
{sources_summary}
"""

        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
            temperature=0.2
        )

        citations = [
            {
                "index": idx + 1,
                "title": s.title,
                "url": s.url,
                "domain": s.domain,
                "source_type": s.source_type,
                "relevance_score": s.relevance_score
            }
            for idx, s in enumerate(sources)
        ]

        return SynthesizedReport(
            title=f"Research Report: {question[:60]}...",
            markdown_content=response.content,
            executive_summary=f"Synthesized research report produced by the {domain.capitalize()} Multi-Agent engine.",
            limitations=[
                f"Investigation conducted under {domain} specialization parameters.",
                "Citations mapped directly to verified external records."
            ],
            citations=citations
        )
