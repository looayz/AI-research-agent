import re
from typing import Any

from app.agents.base import generate_structured
from app.agents.planner.prompts import PLANNER_SYSTEM_PROMPTS, PLANNER_USER_PROMPT
from app.core.config import settings
from app.core.text import clip, keywords
from app.providers.llm.base import LLMProvider
from app.schemas.research import ResearchPlanSchema

QUERY_COUNTS = {"quick": (2, 3), "standard": (3, 4), "deep": (4, 6)}


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _clean_query(query: str) -> str:
    query = re.sub(r"[\"“”«»?]", " ", query)
    return clip(re.sub(r"\s+", " ", query).strip(), 300)


class PlannerAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    @staticmethod
    def query_bounds(depth: str) -> tuple[int, int]:
        low, high = QUERY_COUNTS.get(depth, QUERY_COUNTS["standard"])
        high = max(1, min(high, settings.MAX_SEARCH_QUERIES))
        return min(low, high), high

    @staticmethod
    def _normalize(data: Any, question: str, max_queries: int) -> ResearchPlanSchema:
        if not isinstance(data, dict):
            raise ValueError("plan is not a JSON object")
        queries: list[str] = []
        seen: set[str] = set()
        for raw in _as_str_list(data.get("search_queries")):
            query = _clean_query(raw)
            if query and query.lower() not in seen:
                seen.add(query.lower())
                queries.append(query)
        if not queries:
            raise ValueError("plan has no search queries")
        return ResearchPlanSchema(
            objective=str(data.get("objective") or question).strip(),
            sub_questions=_as_str_list(data.get("sub_questions"))[:6],
            search_queries=queries[:max_queries],
            research_scope=str(data.get("research_scope") or "").strip(),
            constraints=_as_str_list(data.get("constraints"))[:6],
        )

    async def create_plan(self, question: str, domain: str = "general", depth: str = "standard") -> ResearchPlanSchema:
        low, high = self.query_bounds(depth)
        prompt = PLANNER_USER_PROMPT.format(question=question, depth=depth, min_queries=low, max_queries=high)
        return await generate_structured(
            self.llm,
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPTS.get(domain, PLANNER_SYSTEM_PROMPTS["general"]),
            parse=lambda data: self._normalize(data, question, high),
            temperature=0.2,
            max_tokens=1500,
        )

    @staticmethod
    def fallback_plan(question: str, depth: str = "standard") -> ResearchPlanSchema:
        """Used when the model cannot produce a plan: search for the question itself."""
        _, high = PlannerAgent.query_bounds(depth)
        core = " ".join(keywords(question, limit=8)) or question
        queries = list(dict.fromkeys(q for q in (_clean_query(question), _clean_query(core)) if q))[:high]
        return ResearchPlanSchema(
            objective=question,
            sub_questions=[question],
            search_queries=queries,
            research_scope="Automatic fallback plan (the planner output could not be parsed).",
            constraints=[],
        )
