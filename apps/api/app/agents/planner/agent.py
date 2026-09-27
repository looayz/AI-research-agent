import json
from typing import Dict, Any
from app.providers.llm.base import LLMProvider
from app.agents.planner.prompts import PLANNER_SYSTEM_PROMPTS
from app.schemas.research import ResearchPlanSchema


class PlannerAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    async def create_plan(self, question: str, domain: str = "general") -> ResearchPlanSchema:
        system_prompt = PLANNER_SYSTEM_PROMPTS.get(domain, PLANNER_SYSTEM_PROMPTS["general"])

        user_prompt = f"""Generate a research plan for the following research question in the [{domain.upper()}] domain:
"{question}"

Remember to respond with strictly valid JSON only."""

        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1
        )

        try:
            data = json.loads(response.content.strip())
            return ResearchPlanSchema(**data)
        except Exception:
            cleaned = response.content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            return ResearchPlanSchema(**data)
