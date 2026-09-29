from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.text import clip


class EvidenceSource(BaseModel):
    """A persisted source as seen by the verifier and the synthesizer."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    title: str
    domain: str
    source_type: str = "web_article"
    published_at: Optional[str] = None
    content: str = ""
    relevance_score: float = 0.5
    origin: str = "search"


def format_source_block(index: int, source: EvidenceSource, excerpt_chars: int) -> str:
    details = [
        source.domain,
        source.source_type.replace("_", " "),
        f"published {source.published_at[:10]}" if source.published_at else "date unknown",
    ]
    if source.origin == "follow_up":
        details.append("found by a follow-up search")
    elif source.origin == "memory":
        details.append("recalled from a previous investigation")
    return f"[{index}] {source.title}\n{' · '.join(details)}\nURL: {source.url}\nContent:\n{clip(source.content, excerpt_chars)}"


def excerpt_budget(count: int, total_chars: int, low: int, high: int) -> int:
    if count <= 0:
        return high
    return max(low, min(high, total_chars // count))
