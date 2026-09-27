import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, Enum, ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ResearchStatus(str, enum.Enum):
    CREATED = "created"
    PLANNING = "planning"
    SEARCHING = "searching"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchDepth(str, enum.Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ResearchDomain(str, enum.Enum):
    GENERAL = "general"
    ACADEMIC = "academic"
    TECHNICAL = "technical"
    MARKET = "market"


class ClaimStatus(str, enum.Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class Research(Base):
    __tablename__ = "researches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[ResearchDepth] = mapped_column(Enum(ResearchDepth), default=ResearchDepth.STANDARD, nullable=False)
    domain: Mapped[ResearchDomain] = mapped_column(Enum(ResearchDomain), default=ResearchDomain.GENERAL, nullable=False)
    status: Mapped[ResearchStatus] = mapped_column(Enum(ResearchStatus), default=ResearchStatus.CREATED, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Cost / Resource tracking
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    search_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fetch_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runtime_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    plan: Mapped[Optional["ResearchPlan"]] = relationship("ResearchPlan", back_populates="research", uselist=False, cascade="all, delete-orphan")
    queries: Mapped[List["SearchQuery"]] = relationship("SearchQuery", back_populates="research", cascade="all, delete-orphan")
    sources: Mapped[List["Source"]] = relationship("Source", back_populates="research", cascade="all, delete-orphan")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="research", cascade="all, delete-orphan")
    contradictions: Mapped[List["Contradiction"]] = relationship("Contradiction", back_populates="research", cascade="all, delete-orphan")
    events: Mapped[List["ResearchEvent"]] = relationship("ResearchEvent", back_populates="research", cascade="all, delete-orphan")
    report: Mapped[Optional["Report"]] = relationship("Report", back_populates="research", uselist=False, cascade="all, delete-orphan")


class ResearchPlan(Base):
    __tablename__ = "research_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False, unique=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    sub_questions: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    search_queries: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    research_scope: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="plan")


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False)
    sub_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="queries")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="web_article", nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluation_factors: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evaluation_notes: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(JSON, default=list, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="sources")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ClaimStatus] = mapped_column(Enum(ClaimStatus), default=ClaimStatus.SUPPORTED, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    supporting_sources: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    contradicting_sources: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="claims")


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    point_a: Mapped[str] = mapped_column(Text, nullable=False)
    source_a_url: Mapped[str] = mapped_column(Text, nullable=False)
    point_b: Mapped[str] = mapped_column(Text, nullable=False)
    source_b_url: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="contradictions")


class ResearchEvent(Base):
    __tablename__ = "research_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    agent: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="events")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id: Mapped[str] = mapped_column(String(36), ForeignKey("researches.id", ondelete="CASCADE"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[List[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    research: Mapped["Research"] = relationship("Research", back_populates="report")
