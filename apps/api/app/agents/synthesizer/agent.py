import re
from typing import Any, Optional

from pydantic import BaseModel

from app.agents.evidence import EvidenceSource, excerpt_budget
from app.agents.synthesizer.prompts import SYNTHESIZER_SYSTEM_PROMPT, SYNTHESIZER_USER_PROMPT
from app.agents.verifier.agent import DetectedContradiction, VerifiedClaim
from app.core.text import clip
from app.providers.llm.base import LLMError, LLMProvider

_CITE_GROUP_RE = re.compile(r"\[(\d{1,3}(?:\s*[,;–-]\s*\d{1,3})*)\](?!\()")
_CODE_SPLIT_RE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REPEATED_CITE_RE = re.compile(r"(\[\d{1,3}\])(?:\1)+")
_WRAPPED_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", re.DOTALL | re.IGNORECASE)
_LIMITS_RE = re.compile(r"limit|limite|einschr|limitac|limitaz", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+(.*)$")


class SynthesizedReport(BaseModel):
    title: str
    markdown_content: str
    executive_summary: str
    limitations: list[str]
    citations: list[dict[str, Any]]


def _expand_group(group: str) -> list[int]:
    numbers: list[int] = []
    for part in re.split(r"\s*[,;]\s*", group.strip()):
        span = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if span:
            start, end = int(span.group(1)), int(span.group(2))
            if 0 < end - start <= 10:
                numbers.extend(range(start, end + 1))
        elif part.isdigit():
            numbers.append(int(part))
    return numbers


def normalize_citations(markdown: str, source_count: int) -> tuple[str, set[int]]:
    """Rewrite [1, 2] / [1-3] as [1][2][3] and drop numbers that match no source."""
    cited: set[int] = set()

    def replace(match: re.Match) -> str:
        numbers = [n for n in dict.fromkeys(_expand_group(match.group(1))) if 1 <= n <= source_count]
        cited.update(numbers)
        return "".join(f"[{n}]" for n in numbers)

    parts = _CODE_SPLIT_RE.split(markdown)
    for i in range(0, len(parts), 2):  # even parts are outside code
        parts[i] = _REPEATED_CITE_RE.sub(r"\1", _CITE_GROUP_RE.sub(replace, parts[i]))
    return "".join(parts), cited


def strip_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
    text = re.sub(r"\s*" + _CITE_GROUP_RE.pattern, "", text)  # citations (with the space before them)
    text = re.sub(r"[*_`]{1,3}([^*_`]+)[*_`]{1,3}", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    return re.sub(r"[ \t]+", " ", text).strip()


def split_sections(markdown: str) -> tuple[Optional[str], list[tuple[str, str]], str]:
    """Return (H1 title, [(H2 heading, body)], text before the first H2)."""
    title: Optional[str] = None
    sections: list[tuple[str, list[str]]] = []
    preamble: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# ") and title is None and not sections:
            title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return title, [(h, "\n".join(body).strip()) for h, body in sections], "\n".join(preamble).strip()


def _first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        if block.strip() and not block.strip().startswith("#"):
            return block.strip()
    return ""


class SynthesizerAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    @staticmethod
    def build_prompt(
        question: str,
        domain: str,
        sources: list[EvidenceSource],
        claims: list[VerifiedClaim],
        contradictions: list[DetectedContradiction],
        gaps: list[str],
    ) -> str:
        number = {s.url: i + 1 for i, s in enumerate(sources)}
        budget = excerpt_budget(len(sources), 18_000, 400, 1_500)

        def refs(urls: list[str]) -> str:
            return "".join(f"[{number[u]}]" for u in urls if u in number)

        source_blocks = "\n\n".join(
            f"[{i + 1}] {s.title}\n{s.domain} · {s.source_type.replace('_', ' ')}"
            f"{' · published ' + s.published_at[:10] if s.published_at else ''}\n"
            f"URL: {s.url}\nExcerpt: {clip(s.content, budget)}"
            for i, s in enumerate(sources)
        )
        claim_lines = []
        for c in claims:
            line = f"- [{c.status.value}, confidence {c.confidence:.2f}] {c.claim_text}"
            if refs(c.supporting_sources):
                line += f" | supported by {refs(c.supporting_sources)}"
            if refs(c.contradicting_sources):
                line += f" | contradicted by {refs(c.contradicting_sources)}"
            if c.reasoning:
                line += f" | {c.reasoning}"
            claim_lines.append(line)
        contradiction_lines = [
            f'- {c.topic}: "{clip(c.point_a, 200)}" {refs([c.source_a_url])} vs '
            f'"{clip(c.point_b, 200)}" {refs([c.source_b_url])} | {c.explanation}'
            for c in contradictions
        ]
        return SYNTHESIZER_USER_PROMPT.format(
            question=question,
            domain=domain,
            sources=source_blocks or "(no sources)",
            claims="\n".join(claim_lines) or "- (no verified claims)",
            contradictions="\n".join(contradiction_lines) or "- (none detected)",
            gaps="\n".join(f"- {g}" for g in gaps) or "- (none identified)",
        )

    @staticmethod
    def parse_report(raw: str, question: str, sources: list[EvidenceSource]) -> SynthesizedReport:
        markdown = raw.strip()
        wrapped = _WRAPPED_RE.match(markdown)
        if wrapped:
            markdown = wrapped.group(1).strip()
        markdown, cited = normalize_citations(markdown, len(sources))

        title, sections, preamble = split_sections(markdown)
        if not title:
            title = clip(question, 200)
            markdown = f"# {title}\n\n{markdown}"

        summary_source = sections[0][1] if sections else preamble or markdown
        executive_summary = clip(strip_markdown(_first_paragraph(summary_source) or summary_source), 1500)

        limitations: list[str] = []
        for heading, body in sections:
            if _LIMITS_RE.search(heading):
                limitations = [strip_markdown(m.group(1)) for m in map(_BULLET_RE.match, body.splitlines()) if m]
                if not limitations and body.strip():
                    limitations = [clip(strip_markdown(body), 500)]
                break

        citations = [
            {
                "index": i + 1,
                "source_id": s.id,
                "title": s.title,
                "url": s.url,
                "domain": s.domain,
                "source_type": s.source_type,
                "relevance_score": s.relevance_score,
                "cited": (i + 1) in cited,
            }
            for i, s in enumerate(sources)
        ]
        return SynthesizedReport(
            title=clip(strip_markdown(title), 250),
            markdown_content=markdown,
            executive_summary=executive_summary,
            limitations=[item for item in limitations if item][:10],
            citations=citations,
        )

    async def generate_report(
        self,
        question: str,
        sources: list[EvidenceSource],
        *,
        domain: str = "general",
        claims: Optional[list[VerifiedClaim]] = None,
        contradictions: Optional[list[DetectedContradiction]] = None,
        gaps: Optional[list[str]] = None,
    ) -> SynthesizedReport:
        prompt = self.build_prompt(question, domain, sources, claims or [], contradictions or [], gaps or [])
        response = await self.llm.generate(prompt, system_prompt=SYNTHESIZER_SYSTEM_PROMPT, temperature=0.3, max_tokens=5000)
        if len(response.content.strip()) < 80:
            raise LLMError("synthesizer: the model returned an empty or truncated report")
        return self.parse_report(response.content, question, sources)
