from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.research import ResearchStatus, ResearchDepth, ResearchDomain, ClaimStatus


class ResearchCreateRequest(BaseModel):
    question: str = Field(..., min_length=5, description="The complex research question to investigate")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Depth of investigation")
    domain: ResearchDomain = Field(default=ResearchDomain.GENERAL, description="Specialized domain profile")


class ResearchPlanSchema(BaseModel):
    objective: str
    sub_questions: List[str]
    search_queries: List[str]
    research_scope: str
    constraints: List[str] = Field(default_factory=list)


class SourceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    title: str
    domain: str
    content: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: datetime
    source_type: str
    relevance_score: float
    is_excluded: bool
    evaluation_factors: Dict[str, Any]
    evaluation_notes: List[str]


class ClaimSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_text: str
    status: ClaimStatus
    confidence: float
    supporting_sources: List[str]
    contradicting_sources: List[str]
    reasoning: str
    created_at: datetime


class ContradictionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic: str
    point_a: str
    source_a_url: str
    point_b: str
    source_b_url: str
    explanation: str
    created_at: datetime


class SearchQuerySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sub_question: Optional[str]
    query: str
    results_count: int
    is_follow_up: bool


class ReportSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    markdown_content: str
    executive_summary: str
    limitations: List[str]
    citations: List[Dict[str, Any]]
    created_at: datetime


class ResearchEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    agent: str
    data: Dict[str, Any]
    created_at: datetime


class ResearchBasicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    depth: ResearchDepth
    domain: ResearchDomain
    status: ResearchStatus
    error_message: Optional[str] = None
    tokens_used: int
    llm_calls: int
    search_calls: int
    fetch_calls: int
    runtime_seconds: float
    created_at: datetime
    completed_at: Optional[datetime] = None


class ResearchDetailResponse(ResearchBasicResponse):
    plan: Optional[ResearchPlanSchema] = None
    queries: List[SearchQuerySchema] = Field(default_factory=list)
    sources: List[SourceSchema] = Field(default_factory=list)
    claims: List[ClaimSchema] = Field(default_factory=list)
    contradictions: List[ContradictionSchema] = Field(default_factory=list)
    report: Optional[ReportSchema] = None
