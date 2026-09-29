"""Deterministic offline search provider for demo mode and tests.

Results are synthetic but built from the query, so a demo about any topic
stays coherent. They use reserved ``.example`` domains (RFC 2606) and carry
their full text, so nothing is ever fetched over the network.
"""

import hashlib
import re

from app.core.text import detect_language, keywords, strip_accents
from app.providers.search.base import SearchProvider, SearchResult

_DOMAINS = {
    "general": [
        ("encyclopedia.example", "encyclopedia"),
        ("news-review.example", "news"),
        ("policy-institute.example", "report"),
    ],
    "academic": [
        ("journal-of-studies.example", "peer_reviewed_paper"),
        ("preprints.example", "preprint"),
        ("university-lab.example", "academic_publication"),
    ],
    "technical": [
        ("docs.example", "technical_documentation"),
        ("engineering-blog.example", "blog"),
        ("code-forge.example", "repository"),
    ],
    "market": [
        ("market-insights.example", "market_report"),
        ("finance-daily.example", "news"),
        ("industry-analysis.example", "analyst_report"),
    ],
}

# angle -> (English title, French title, English body, French body)
_ANGLES = {
    "overview": (
        "{Topic}: an overview",
        "{Topic} : vue d'ensemble",
        "{Topic} has attracted growing attention in recent years. Practitioners describe it as a trade-off between capability, cost and complexity, and most sources agree on the core definitions.",
        "{Topic} suscite un intérêt croissant depuis quelques années. Les praticiens le décrivent comme un compromis entre capacités, coût et complexité, et la plupart des sources s'accordent sur les définitions de base.",
    ),
    "benefits": (
        "Benefits and limitations of {topic}",
        "Avantages et limites : {topic}",
        "Reported benefits include better efficiency and new capabilities. Reported limitations include higher costs, integration effort and a shortage of skilled people.",
        "Les avantages rapportés incluent une meilleure efficacité et de nouvelles capacités. Les limites citées sont un coût plus élevé, un effort d'intégration et un manque de compétences.",
    ),
    "evidence": (
        "What the evidence says about {topic}",
        "Ce que disent les données sur {topic}",
        "Controlled studies show positive but modest effects. The strongest evidence comes from a few large deployments; smaller studies report mixed results and long-term data is scarce.",
        "Les études contrôlées montrent des effets positifs mais modestes. Les preuves les plus solides viennent de quelques grands déploiements ; les petites études sont plus mitigées et les données à long terme sont rares.",
    ),
    "critique": (
        "Critical perspectives on {topic}",
        "Regards critiques sur {topic}",
        "Critics argue that the benefits of {topic} are overstated and that long-term costs are rarely measured. They point to contradictory results between early and recent studies.",
        "Les critiques estiment que les bénéfices de {topic} sont surestimés et que les coûts à long terme sont rarement mesurés. Ils soulignent des résultats contradictoires entre études anciennes et récentes.",
    ),
    "practice": (
        "{Topic} in practice: case studies",
        "{Topic} en pratique : études de cas",
        "Case studies from several sectors show that outcomes depend heavily on implementation quality and on the maturity of the teams involved.",
        "Des études de cas dans plusieurs secteurs montrent que les résultats dépendent fortement de la qualité de mise en œuvre et de la maturité des équipes.",
    ),
    "outlook": (
        "The outlook for {topic}",
        "Perspectives : {topic}",
        "Analysts expect adoption to keep growing, although forecasts diverge widely, from {g1}% to {g2}% annual growth depending on the scenario.",
        "Les analystes prévoient une adoption croissante, mais les prévisions divergent fortement, de {g1} % à {g2} % de croissance annuelle selon les scénarios.",
    ),
}

_FIGURES = {
    "en": "Key figures: about {p1}% of the organisations surveyed reported measurable benefits, while {p2}% reported significant obstacles. The authors caution that results vary with context.",
    "fr": "Chiffres clés : environ {p1} % des organisations interrogées rapportent des bénéfices mesurables, tandis que {p2} % signalent des obstacles importants. Les auteurs rappellent que les résultats varient selon le contexte.",
}
_DISCLAIMER = {
    "en": "Note: synthetic demo content generated offline (mock search provider).",
    "fr": "Note : contenu de démonstration synthétique généré hors ligne (fournisseur de recherche fictif).",
}


# Angle words the demo planner appends to queries; not part of the subject.
_ANGLE_WORDS = frozenset(
    """overview benefits limitations evidence study studies criticism debate case outlook forecast long-term
    independent replication meta-analysis vue ensemble avantages limites etude étude donnees données critiques
    debat débat etudes études cas perspectives previsions prévisions long terme replication réplication
    independante indépendante meta-analyse méta-analyse""".split()
)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", strip_accents(text).lower()).strip("-")[:60] or "topic"


class MockSearchProvider(SearchProvider):
    name = "mock"

    async def search(self, query: str, max_results: int = 5, domain: str = "general") -> list[SearchResult]:
        lang = detect_language(query)
        words = [w for w in keywords(query, limit=12) if w.lower() not in _ANGLE_WORDS]
        topic = " ".join(words[:5]) or " ".join(keywords(query, limit=5)) or query.strip()
        digest = hashlib.md5(f"{domain}|{query}".encode()).hexdigest()
        seed = int(digest[:8], 16)
        angles = list(_ANGLES)
        domains = _DOMAINS.get(domain, _DOMAINS["general"])

        results = []
        for i in range(min(max_results, 3)):
            angle = angles[(seed + i) % len(angles)]
            title_en, title_fr, body_en, body_fr = _ANGLES[angle]
            host, source_type = domains[(seed + i) % len(domains)]
            values = {
                "topic": topic,
                "Topic": topic[:1].upper() + topic[1:],
                "g1": 3 + (seed >> (i + 1)) % 5,
                "g2": 12 + (seed >> (i + 3)) % 20,
            }
            title = (title_fr if lang == "fr" else title_en).format(**values)
            body = (body_fr if lang == "fr" else body_en).format(**values)
            figures = _FIGURES[lang].format(p1=35 + (seed >> i) % 40, p2=10 + (seed >> (i + 2)) % 30)
            content = f"{title}\n\n{body}\n\n{figures}\n\n{_DISCLAIMER[lang]}"
            results.append(
                SearchResult(
                    title=title,
                    url=f"https://{host}/{angle}/{_slug(topic)}-{digest[i * 2 : i * 2 + 6]}",
                    snippet=body[:200],
                    content=content,
                    published_date=f"202{4 + (seed + i) % 2}-{1 + (seed >> i) % 12:02d}-{1 + (seed >> (i + 4)) % 28:02d}",
                    score=round(0.95 - 0.1 * i, 2),
                    source_type=source_type,
                    provider=self.name,
                )
            )
        return results
