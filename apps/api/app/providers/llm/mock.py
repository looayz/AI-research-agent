"""Deterministic offline LLM for demo mode and tests.

It reads the prompts built by the agents (sources, claims, rounds...) and
answers with plausible, question-specific output, so the whole pipeline can
be exercised end-to-end without any API key. Content is explicitly flagged
as synthetic in the generated report.
"""

import asyncio
import json
import re
from typing import Optional

from app.core.config import settings
from app.core.text import detect_language, keywords
from app.providers.llm.base import LLMProvider, LLMResponse

_QUESTION_RE = re.compile(r'"""(.*?)"""', re.DOTALL)
_SOURCE_RE = re.compile(r"^\[(\d+)\] (.+)$", re.MULTILINE)
_RANGE_RE = re.compile(r"between (\d+) and (\d+)")
_ROUND_RE = re.compile(r"round (\d+) of (\d+)", re.IGNORECASE)
_CLAIM_RE = re.compile(r"^- \[(\w+), confidence ([\d.]+)\] (.+)$", re.MULTILINE)
_CONTRA_RE = re.compile(r'^- (.+?): "(.+?)" ((?:\[\d+\])*) vs "(.+?)" ((?:\[\d+\])*) \| (.*)$', re.MULTILINE)

_T = {
    "en": {
        "objective": "Establish what reliable sources say about: {question}",
        "subs": [
            "What is {topic} and what are its core characteristics?",
            "What benefits and limitations of {topic} are documented?",
            "Where do sources disagree about {topic}, and why?",
            "What does the evidence say about the long-term impact of {topic}?",
        ],
        "queries": [
            "{topic} overview",
            "{topic} benefits limitations",
            "{topic} evidence study",
            "{topic} criticism debate",
            "{topic} case studies",
            "{topic} outlook forecast",
        ],
        "scope": "Recent sources (last five years), all regions, focusing on documented evidence rather than opinion.",
        "constraints": ["Prefer primary and peer-reviewed sources", "Flag figures that only one source reports"],
        "claims": [
            (
                "Several independent sources agree on the core definition and main characteristics of {topic}.",
                "The overview and reference sources describe it consistently.",
            ),
            (
                "The documented benefits of {topic} come with real costs, such as integration effort and required skills.",
                "Benefits and limitations are reported by more than one source.",
            ),
            (
                "The size of the effects attributed to {topic} varies widely between studies and contexts.",
                "Figures differ between sources, which use different methods and samples.",
            ),
            (
                "Long-term, independently replicated data on {topic} is still limited.",
                "No source provides long-term measurements; the claim cannot be settled yet.",
            ),
            (
                "Follow-up searches found additional long-term evidence on {topic}, but replication remains limited.",
                "The follow-up sources partly fill the long-term data gap.",
            ),
            (
                "Claims that {topic} has no significant drawbacks are contradicted by critical analyses.",
                "Critical sources document drawbacks that promotional material omits.",
            ),
        ],
        "contradiction": (
            "Magnitude of the benefits",
            "Reports strong, measurable benefits.",
            "Finds modest or context-dependent effects.",
            "The sources use different methodologies, time frames and populations.",
        ),
        "gap": "Long-term, independently replicated data on {topic}",
        "followups": ["{topic} long-term evidence", "{topic} independent replication study", "{topic} meta-analysis"],
        "report": {
            "title": "{Topic}: evidence review",
            "summary_h": "Executive summary",
            "summary": "This report reviews {n} sources about “{question}”. Of {total} key claims, {supported} are supported by the evidence, {partial} partially supported and {weak} uncertain or disputed. {debate}These conclusions come from the offline demo mode and are illustrative only.",
            "debate": "The main debate concerns {contradiction}. ",
            "findings_h": "Key findings",
            "evidence_h": "Evidence and analysis",
            "evidence": "Sources were weighted by authority, relevance, depth and freshness. The most relevant ones are “{s1}” {r1} and “{s2}” {r2}. Claims backed by several independent sources were rated higher than claims resting on a single source.",
            "contra_h": "Contradictions and debates",
            "no_contra": "No direct contradiction between sources was detected.",
            "limits_h": "Limitations",
            "limits": [
                "Demo mode: the sources and the analysis are synthetic and were generated offline.",
                "Evidence comes from a limited number of sources and has not been reviewed by a human.",
            ],
            "conclusion_h": "Conclusion",
            "conclusion": "The evidence supports a nuanced view of {topic}: its main characteristics are well established, while the size and durability of its effects depend on context. Connect a real LLM and search provider to run this investigation on live sources.",
        },
    },
    "fr": {
        "objective": "Établir ce que disent des sources fiables sur : {question}",
        "subs": [
            "Qu'est-ce que {topic} et quelles en sont les caractéristiques principales ?",
            "Quels avantages et quelles limites de {topic} sont documentés ?",
            "Sur quels points les sources divergent-elles à propos de {topic}, et pourquoi ?",
            "Que disent les données sur l'impact à long terme de {topic} ?",
        ],
        "queries": [
            "{topic} vue d'ensemble",
            "{topic} avantages limites",
            "{topic} étude données",
            "{topic} critiques débat",
            "{topic} études de cas",
            "{topic} perspectives prévisions",
        ],
        "scope": "Sources récentes (cinq dernières années), toutes régions, en privilégiant les données documentées plutôt que les opinions.",
        "constraints": [
            "Privilégier les sources primaires et évaluées par des pairs",
            "Signaler les chiffres rapportés par une seule source",
        ],
        "claims": [
            (
                "Plusieurs sources indépendantes s'accordent sur la définition et les caractéristiques principales de {topic}.",
                "Les sources de référence le décrivent de façon cohérente.",
            ),
            (
                "Les avantages documentés de {topic} s'accompagnent de coûts réels, comme l'effort d'intégration et les compétences nécessaires.",
                "Avantages et limites sont rapportés par plusieurs sources.",
            ),
            (
                "L'ampleur des effets attribués à {topic} varie fortement selon les études et les contextes.",
                "Les chiffres diffèrent entre des sources aux méthodes et échantillons différents.",
            ),
            (
                "Les données à long terme, répliquées de façon indépendante, sur {topic} restent limitées.",
                "Aucune source ne fournit de mesures à long terme ; la question ne peut pas encore être tranchée.",
            ),
            (
                "Les recherches complémentaires apportent des données à long terme sur {topic}, mais la réplication reste limitée.",
                "Les sources complémentaires comblent en partie le manque de données à long terme.",
            ),
            (
                "L'idée que {topic} n'aurait pas d'inconvénient notable est contredite par les analyses critiques.",
                "Les sources critiques documentent des inconvénients absents des présentations promotionnelles.",
            ),
        ],
        "contradiction": (
            "Ampleur des bénéfices",
            "Rapporte des bénéfices importants et mesurables.",
            "Constate des effets modestes ou dépendants du contexte.",
            "Les sources utilisent des méthodes, des périodes et des populations différentes.",
        ),
        "gap": "Données à long terme, répliquées de façon indépendante, sur {topic}",
        "followups": ["{topic} données long terme", "{topic} étude réplication indépendante", "{topic} méta-analyse"],
        "report": {
            "title": "{Topic} : revue des preuves",
            "summary_h": "Résumé exécutif",
            "summary": "Ce rapport examine {n} sources sur « {question} ». Sur {total} affirmations clés : {supported} étayées par les preuves, {partial} partiellement étayées et {weak} incertaines ou contestées. {debate}Ces conclusions proviennent du mode démo hors ligne et sont purement illustratives.",
            "debate": "Le principal débat porte sur : {contradiction}. ",
            "findings_h": "Principaux résultats",
            "evidence_h": "Preuves et analyse",
            "evidence": "Les sources ont été pondérées selon leur autorité, leur pertinence, leur profondeur et leur fraîcheur. Les plus pertinentes sont « {s1} » {r1} et « {s2} » {r2}. Les affirmations appuyées par plusieurs sources indépendantes ont reçu un meilleur score que celles qui reposent sur une seule source.",
            "contra_h": "Contradictions et débats",
            "no_contra": "Aucune contradiction directe entre les sources n'a été détectée.",
            "limits_h": "Limites",
            "limits": [
                "Mode démo : les sources et l'analyse sont synthétiques et générées hors ligne.",
                "Les preuves proviennent d'un nombre limité de sources et n'ont pas été relues par un humain.",
            ],
            "conclusion_h": "Conclusion",
            "conclusion": "Les preuves invitent à une vision nuancée de {topic} : ses caractéristiques principales sont bien établies, tandis que l'ampleur et la durabilité de ses effets dépendent du contexte. Connectez un vrai LLM et un vrai moteur de recherche pour mener cette enquête sur des sources réelles.",
        },
    },
}


def _question(prompt: str) -> str:
    match = _QUESTION_RE.search(prompt)
    return match.group(1).strip() if match else prompt.strip()[:300]


# Words that describe the kind of question rather than its subject.
_GENERIC = frozenset(
    """tradeoffs trade-offs tradeoff advantages disadvantages benefits limits limitations pros cons impact impacts
    effect effects comparison compare best main key modern approaches approach current state role
    avantages inconvenients inconvénients limites effets comparaison meilleures meilleurs principaux principales
    approches modernes actuel actuelle etat état""".split()
)


def _topic(question: str) -> str:
    words = [w for w in keywords(question, limit=10) if w.lower() not in _GENERIC]
    return " ".join(words[:5]) or " ".join(keywords(question, limit=5)) or question


def _refs(numbers: list[int]) -> str:
    return "".join(f"[{n}]" for n in numbers)


class MockLLMProvider(LLMProvider):
    name = "mock"
    model = "mock-1"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> LLMResponse:
        if settings.MOCK_LATENCY_SECONDS > 0:
            await asyncio.sleep(settings.MOCK_LATENCY_SECONDS)
        system = system_prompt or ""
        if "Research Planner" in system:
            content = json.dumps(self._plan(prompt), ensure_ascii=False)
        elif "Evidence Verifier" in system:
            content = json.dumps(self._verify(prompt), ensure_ascii=False)
        elif "Gap Analyzer" in system:
            content = json.dumps(self._gaps(prompt), ensure_ascii=False)
        elif "Research Synthesizer" in system:
            content = self._report(prompt)
        else:
            content = "Simulated response (mock LLM provider)."
        return LLMResponse(content=content, tokens_used=(len(prompt) + len(system) + len(content)) // 4, model=self.model)

    def _plan(self, prompt: str) -> dict:
        question = _question(prompt)
        t = _T[detect_language(question)]
        topic = _topic(question)
        bounds = _RANGE_RE.search(prompt)
        count = int(bounds.group(2)) if bounds else 3
        return {
            "objective": t["objective"].format(question=question),
            "sub_questions": [s.format(topic=topic) for s in t["subs"]],
            "search_queries": [q.format(topic=topic) for q in t["queries"][:count]],
            "research_scope": t["scope"],
            "constraints": t["constraints"],
        }

    def _verify(self, prompt: str) -> dict:
        question = _question(prompt)
        t = _T[detect_language(question)]
        topic = _topic(question)
        numbers = [int(n) for n, _ in _SOURCE_RE.findall(prompt)]
        n = len(numbers) or 1
        follow_up = [int(m.group(1)) for m in re.finditer(r"^\[(\d+)\] .+\n.*follow-up search", prompt, re.MULTILINE)]
        bounds = _RANGE_RE.search(prompt)
        max_claims = int(bounds.group(2)) if bounds else 5

        def claim(i: int, status: str, confidence: float, supporting: list[int], contradicting: tuple[int, ...] = ()) -> dict:
            text, reasoning = t["claims"][i]
            return {
                "claim_text": text.format(topic=topic),
                "status": status,
                "confidence": confidence,
                "supporting_sources": [s for s in supporting if s <= n],
                "contradicting_sources": [s for s in contradicting if s <= n],
                "reasoning": reasoning,
            }

        claims = [
            claim(0, "supported", 0.9, [1, 2]),
            claim(1, "supported", 0.78, [2, 3]),
            claim(2, "partially_supported", 0.62, [3], (n,) if n > 3 else ()),
        ]
        if follow_up:
            claims.append(claim(4, "partially_supported", 0.66, follow_up[:3]))
        else:
            claims.append(claim(3, "insufficient_evidence", 0.4, []))
        if max_claims >= 9 and n >= 4:
            claims.append(claim(5, "contradicted", 0.7, [], (n - 1,)))

        topic_label, point_a, point_b, explanation = t["contradiction"]
        contradictions = (
            [
                {
                    "topic": topic_label,
                    "point_a": point_a,
                    "source_a": 1,
                    "point_b": point_b,
                    "source_b": n,
                    "explanation": explanation,
                }
            ]
            if n >= 2
            else []
        )
        return {"claims": claims, "contradictions": contradictions}

    def _gaps(self, prompt: str) -> dict:
        question = _question(prompt)
        t = _T[detect_language(question)]
        topic = _topic(question)
        match = _ROUND_RE.search(prompt)
        round_number, max_rounds = (int(match.group(1)), int(match.group(2))) if match else (1, 1)
        weak = "[insufficient_evidence" in prompt or "[partially_supported" in prompt
        if not weak or round_number > min(max_rounds, 2):
            return {"is_sufficient": True, "gaps_identified": [], "follow_up_queries": []}
        query = t["followups"][(round_number - 1) % len(t["followups"])].format(topic=topic)
        return {"is_sufficient": False, "gaps_identified": [t["gap"].format(topic=topic)], "follow_up_queries": [query]}

    def _report(self, prompt: str) -> str:
        question = _question(prompt)
        lang = detect_language(question)
        r = _T[lang]["report"]
        topic = _topic(question)
        topic_cap = topic[:1].upper() + topic[1:]
        sources = _SOURCE_RE.findall(prompt)
        n = len(sources)
        claims = _CLAIM_RE.findall(prompt)
        contradictions = _CONTRA_RE.findall(prompt)

        statuses = [c[0] for c in claims]
        supported = statuses.count("supported")
        partial = statuses.count("partially_supported")
        weak = len(statuses) - supported - partial
        debate = r["debate"].format(contradiction=contradictions[0][0].lower()) if contradictions else ""

        lines = [
            f"# {r['title'].format(Topic=topic_cap)}",
            "",
            f"## {r['summary_h']}",
            r["summary"].format(
                n=n, question=question, supported=supported, total=len(claims), partial=partial, weak=weak, debate=debate
            ),
            "",
            f"## {r['findings_h']}",
        ]
        for i, (status, confidence, rest) in enumerate(claims, start=1):
            text, *parts = rest.split(" | ")
            refs = next((p.split("by ", 1)[1] for p in parts if p.startswith("supported by ")), "")
            reasoning = next((p for p in parts if not p.startswith(("supported by ", "contradicted by "))), "")
            lines += [
                "",
                f"### {i}. {text}",
                f"{reasoning} {refs}".strip() + f" ({status.replace('_', ' ')}, {float(confidence):.0%})",
            ]
        s1 = sources[0][1] if sources else "-"
        s2 = sources[1][1] if n > 1 else s1
        lines += [
            "",
            f"## {r['evidence_h']}",
            r["evidence"].format(s1=s1, s2=s2, r1="[1]" if n else "", r2="[2]" if n > 1 else ""),
        ]
        lines += ["", f"## {r['contra_h']}"]
        if contradictions:
            for topic_label, point_a, refs_a, point_b, refs_b, explanation in contradictions:
                lines.append(f"- **{topic_label}**: {point_a} {refs_a} / {point_b} {refs_b}. {explanation}")
        else:
            lines.append(r["no_contra"])
        lines += ["", f"## {r['limits_h']}"] + [f"- {item}" for item in r["limits"]]
        lines += ["", f"## {r['conclusion_h']}", r["conclusion"].format(topic=topic)]
        return "\n".join(lines)
