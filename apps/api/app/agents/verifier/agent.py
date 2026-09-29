from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import generate_structured
from app.agents.evidence import EvidenceSource, excerpt_budget, format_source_block
from app.agents.verifier.prompts import VERIFIER_SYSTEM_PROMPT, VERIFIER_USER_PROMPT
from app.core.text import clip, normalize_url
from app.models.research import ClaimStatus
from app.providers.llm.base import LLMProvider

CLAIM_COUNTS = {"quick": (3, 5), "standard": (4, 7), "deep": (5, 9)}

_STATUS_ALIASES = {
    "supported": ClaimStatus.SUPPORTED,
    "verified": ClaimStatus.SUPPORTED,
    "true": ClaimStatus.SUPPORTED,
    "partially_supported": ClaimStatus.PARTIALLY_SUPPORTED,
    "partial": ClaimStatus.PARTIALLY_SUPPORTED,
    "partly_supported": ClaimStatus.PARTIALLY_SUPPORTED,
    "mixed": ClaimStatus.PARTIALLY_SUPPORTED,
    "contradicted": ClaimStatus.CONTRADICTED,
    "refuted": ClaimStatus.CONTRADICTED,
    "disputed": ClaimStatus.CONTRADICTED,
    "false": ClaimStatus.CONTRADICTED,
    "insufficient_evidence": ClaimStatus.INSUFFICIENT_EVIDENCE,
    "insufficient": ClaimStatus.INSUFFICIENT_EVIDENCE,
    "unverified": ClaimStatus.INSUFFICIENT_EVIDENCE,
    "unsupported": ClaimStatus.INSUFFICIENT_EVIDENCE,
    "unknown": ClaimStatus.INSUFFICIENT_EVIDENCE,
}


class VerifiedClaim(BaseModel):
    claim_text: str
    status: ClaimStatus = ClaimStatus.INSUFFICIENT_EVIDENCE
    confidence: float = 0.5
    supporting_sources: list[str] = Field(default_factory=list)
    contradicting_sources: list[str] = Field(default_factory=list)
    reasoning: str = ""


class DetectedContradiction(BaseModel):
    topic: str
    point_a: str
    source_a_url: str
    point_b: str
    source_b_url: str
    explanation: str


class VerificationResult(BaseModel):
    claims: list[VerifiedClaim] = Field(default_factory=list)
    contradictions: list[DetectedContradiction] = Field(default_factory=list)


def coerce_status(value: Any) -> ClaimStatus:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _STATUS_ALIASES.get(key, ClaimStatus.INSUFFICIENT_EVIDENCE)


def coerce_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    if 1 < number <= 100 and number.is_integer():
        number /= 100  # a percentage such as 85
    return round(max(0.0, min(1.0, number)), 3)


class SourceIndex:
    """Maps the numbers shown to the model back to source URLs."""

    def __init__(self, sources: list[EvidenceSource]):
        self.sources = sources
        self._by_url = {normalize_url(s.url): s.url for s in sources}

    def resolve(self, ref: Any) -> str | None:
        if ref is None or isinstance(ref, bool):
            return None
        if isinstance(ref, (int, float)):
            index = int(ref)
        else:
            text = str(ref).strip().strip("[]").strip()
            if not text.isdigit():
                return self._by_url.get(normalize_url(text))
            index = int(text)
        return self.sources[index - 1].url if 1 <= index <= len(self.sources) else None

    def resolve_all(self, refs: Any) -> list[str]:
        if not isinstance(refs, list):
            refs = [refs] if refs not in (None, "") else []
        return list(dict.fromkeys(url for url in (self.resolve(r) for r in refs) if url))


class VerifierAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    @staticmethod
    def build_prompt(question: str, sources: list[EvidenceSource], depth: str) -> str:
        low, high = CLAIM_COUNTS.get(depth, CLAIM_COUNTS["standard"])
        budget = excerpt_budget(len(sources), 28_000, 600, 2_500)
        blocks = "\n\n".join(format_source_block(i + 1, s, budget) for i, s in enumerate(sources))
        return VERIFIER_USER_PROMPT.format(question=question, min_claims=low, max_claims=high, sources=blocks)

    @staticmethod
    def _normalize(data: Any, index: SourceIndex, max_claims: int) -> VerificationResult:
        if not isinstance(data, dict):
            raise ValueError("verification is not a JSON object")
        raw_claims = data.get("claims")
        if not isinstance(raw_claims, list):
            raise ValueError("missing 'claims' list")

        claims: list[VerifiedClaim] = []
        for raw in raw_claims:
            if not isinstance(raw, dict) or not str(raw.get("claim_text") or raw.get("claim") or "").strip():
                continue
            supporting = index.resolve_all(raw.get("supporting_sources"))
            contradicting = [u for u in index.resolve_all(raw.get("contradicting_sources")) if u not in supporting]
            status = coerce_status(raw.get("status"))
            # A claim cannot be "supported" without any valid supporting source.
            if status == ClaimStatus.SUPPORTED and not supporting:
                status = ClaimStatus.INSUFFICIENT_EVIDENCE
            claims.append(
                VerifiedClaim(
                    claim_text=str(raw.get("claim_text") or raw.get("claim")).strip(),
                    status=status,
                    confidence=coerce_confidence(raw.get("confidence")),
                    supporting_sources=supporting,
                    contradicting_sources=contradicting,
                    reasoning=str(raw.get("reasoning") or "").strip(),
                )
            )

        contradictions: list[DetectedContradiction] = []
        for raw in data.get("contradictions") or []:
            if not isinstance(raw, dict):
                continue
            point_a, point_b = str(raw.get("point_a") or "").strip(), str(raw.get("point_b") or "").strip()
            if not point_a or not point_b:
                continue
            contradictions.append(
                DetectedContradiction(
                    topic=clip(str(raw.get("topic") or "Disagreement between sources"), 255),
                    point_a=point_a,
                    source_a_url=index.resolve(raw.get("source_a", raw.get("source_a_url"))) or "",
                    point_b=point_b,
                    source_b_url=index.resolve(raw.get("source_b", raw.get("source_b_url"))) or "",
                    explanation=str(raw.get("explanation") or "").strip(),
                )
            )
        return VerificationResult(claims=claims[:max_claims], contradictions=contradictions[:6])

    async def verify(self, question: str, sources: list[EvidenceSource], depth: str = "standard") -> VerificationResult:
        if not sources:
            return VerificationResult()
        index = SourceIndex(sources)
        _, high = CLAIM_COUNTS.get(depth, CLAIM_COUNTS["standard"])
        return await generate_structured(
            self.llm,
            prompt=self.build_prompt(question, sources, depth),
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            parse=lambda data: self._normalize(data, index, high + 2),
            temperature=0.1,
            max_tokens=4000,
        )
