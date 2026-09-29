from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.text import clip
from app.models.research import ClaimStatus, ResearchDepth, ResearchDomain, ResearchStatus


class ResearchCreateRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=2000, description="The research question to investigate")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="quick | standard | deep")
    domain: ResearchDomain = Field(default=ResearchDomain.GENERAL, description="general | academic | technical | market")

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 5:
            raise ValueError("The question must contain at least 5 characters")
        return value


class ResearchPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    objective: str
    sub_questions: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    research_scope: str = ""
    constraints: list[str] = Field(default_factory=list)


class SourceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    research_id: str
    url: str
    title: str
    domain: str
    published_at: Optional[str] = None
    retrieved_at: datetime
    source_type: str
    relevance_score: float
    is_excluded: bool
    evaluation_factors: dict[str, Any] = Field(default_factory=dict)
    evaluation_notes: list[str] = Field(default_factory=list)
    origin: str = "search"
    origin_query: Optional[str] = None
    fetch_status: str = "ok"
    content: str = Field(default="", exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def excerpt(self) -> str:
        return clip(self.content, 600)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_length(self) -> int:
        return len(self.content)


class SourceDetailSchema(SourceSchema):
    content: str = ""


class ClaimSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_text: str
    status: ClaimStatus
    confidence: float
    supporting_sources: list[str]
    contradicting_sources: list[str]
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
    sub_question: Optional[str] = None
    query: str
    results_count: int
    is_follow_up: bool
    iteration: int = 0


class ReportSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    markdown_content: str
    executive_summary: str
    limitations: list[str]
    citations: list[dict[str, Any]]
    created_at: datetime


class ResearchEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seq: int
    event_type: str
    agent: str
    data: dict[str, Any]
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
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ResearchSummaryResponse(ResearchBasicResponse):
    """Lightweight item for the history list (counts instead of full content)."""

    report_title: Optional[str] = None
    executive_summary: Optional[str] = None
    source_count: int = 0
    claim_count: int = 0
    contradiction_count: int = 0
    follow_up_count: int = 0


class ResearchListResponse(BaseModel):
    items: list[ResearchSummaryResponse]
    total: int
    limit: int
    offset: int


class ResearchDetailResponse(ResearchBasicResponse):
    plan: Optional[ResearchPlanSchema] = None
    queries: list[SearchQuerySchema] = Field(default_factory=list)
    sources: list[SourceSchema] = Field(default_factory=list)
    claims: list[ClaimSchema] = Field(default_factory=list)
    contradictions: list[ContradictionSchema] = Field(default_factory=list)
    events: list[ResearchEventSchema] = Field(default_factory=list)
    report: Optional[ReportSchema] = None
