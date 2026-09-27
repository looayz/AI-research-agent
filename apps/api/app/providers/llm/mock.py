import json
from typing import Optional
from app.providers.llm.base import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        # Gap Analyzer request
        if "gap analyzer" in (system_prompt or "").lower() or "evidence sufficiency" in prompt.lower():
            mock_gaps = {
                "is_sufficient": False,
                "gaps_identified": [
                    "Données empiriques sur la rétention des structures algorithmiques sans complétion automatique."
                ],
                "follow_up_queries": [
                    "empirical study python syntax retention without copilot ai"
                ]
            }
            return LLMResponse(content=json.dumps(mock_gaps, ensure_ascii=False), tokens_used=95)

        # Planner request
        if "planner" in (system_prompt or "").lower() or "research plan" in prompt.lower():
            mock_plan = {
                "objective": "Comprendre les approches pédagogiques et outillages modernes pour l'apprentissage efficace de Python.",
                "sub_questions": [
                    "Quelles sont les approches d'apprentissage actif (projets, katas) vs académique ?",
                    "Quel est l'impact des assistants IA (Copilot, ChatGPT) sur la courbe d'apprentissage ?",
                    "Quels sont les pièges et limites documentés des différentes méthodologies ?"
                ],
                "search_queries": [
                    "best practices learning python modern approaches project-based",
                    "ai assisted python learning benefits pitfalls research",
                    "comparative study python programming education methods"
                ],
                "research_scope": "Approches modernes d'apprentissage de Python (2020-2026), pédagogie active, intégration IA.",
                "constraints": ["Sources vérifiées uniquement", "Identifier les compromis de chaque méthode"]
            }
            return LLMResponse(content=json.dumps(mock_plan, ensure_ascii=False), tokens_used=120)

        # Verifier request
        if "verifier" in (system_prompt or "").lower() or "evidence to cross-check" in prompt.lower():
            mock_verification = {
                "claims": [
                    {
                        "claim_text": "L'approche par projet (Project-Based Learning) assure une rétention conceptuelle supérieure à la lecture passive.",
                        "status": "supported",
                        "confidence": 0.94,
                        "supporting_sources": ["https://docs.python.org/3/tutorial/index.html", "https://realpython.com/learning-paths/python-foundations/"],
                        "contradicting_sources": [],
                        "reasoning": "Consensus net entre documentation officielle et études didactiques."
                    },
                    {
                        "claim_text": "L'assistance IA améliore la vitesse de déblocage des débutants mais nuit à l'autonomie conceptuelle si mal encadrée.",
                        "status": "partially_supported",
                        "confidence": 0.83,
                        "supporting_sources": ["https://arxiv.org/abs/2306.01234"],
                        "contradicting_sources": [],
                        "reasoning": "Des études récentes confirment le gain de productivité immédiat mais signalent un déficit de résolution autonome."
                    }
                ],
                "contradictions": [
                    {
                        "topic": "Usage précoce de frameworks et librairies externes",
                        "point_a": "Immersion directe dans les packages populaires (Requests, Pandas) pour maintenir la motivation par le résultat visible.",
                        "source_a_url": "https://realpython.com/learning-paths/python-foundations/",
                        "point_b": "Interdiction des bibliothèques externes avant la maîtrise intégrale des algorithmes et types natifs.",
                        "source_b_url": "https://docs.python.org/3/tutorial/index.html",
                        "explanation": "Opposition classique entre formation professionnelle pragmatique et enseignement académique fondamental."
                    }
                ]
            }
            return LLMResponse(content=json.dumps(mock_verification, ensure_ascii=False), tokens_used=210)

        # Synthesizer request
        if "synthesizer" in (system_prompt or "").lower() or "research report" in prompt.lower():
            mock_report = """# Research Report: Approches Modernes pour Apprendre Python

## Executive Summary
L'apprentissage contemporain de Python a évolué d'une mémorisation syntaxique vers une pédagogie orientée projet assistée par IA. La combinaison d'exercices pratiques guidés et de validation de code immédiate offre les taux de rétention les plus élevés.

## Research Question
Quelles sont les approches modernes pour apprendre Python efficacement, avec leurs avantages, limites et sources ?

## Methodology
Investigation multi-sources combinant documentation officielle, retours d'expérience pédagogiques et études comparatives sur l'enseignement de la programmation avec analyse itérative des lacunes de preuves.

## Key Findings
### 1. Apprentissage par la pratique (Project-Based Learning)
Construire des projets concrets dès les premières semaines maximise l'ancrage mémoriel et la motivation [1][2].

### 2. Intégration raisonnée des assistants IA
L'usage de l'IA pour déboguer et expliquer les erreurs accélère la progression, mais une dépendance totale réduit l'apprentissage des fondamentaux algorithmiques [3].

## Evidence & Verified Claims
- **Rétention active** : L'approche par projet est validée avec 94% de confiance à travers la documentation et les retours d'écoles d'ingénieurs [1][2].
- **Impact IA** : Gain de temps de 30% dans la résolution de bugs syntaxiques avec explications guidées, compensé par un risque de perte d'esprit critique si la génération de code n'est pas interrogée [3].

## Contradictions
Une divergence marquée existe concernant le calendrier d'introduction des bibliothèques tierces :
- D'un côté, les approches modernes préconisent l'usage immédiat de modules externes pour créer des applications concrètes motivantes [2].
- De l'autre, les recommandations académiques insistent sur une maîtrise pure de la syntaxe native et des structures de base avant tout composant externe [1].
- **Explication** : Cette divergence provient des objectifs visés : employabilité rapide versus rigueur conceptuelle d'ingénierie logicielle.

## Limitations
L'efficacité d'une approche dépend fortement du bagage mathématique ou logique préalable de l'apprenant.

## Conclusion
L'approche hybride « projets ciblés + feedback assisté » constitue aujourd'hui le compromis optimal entre rapidité de montée en compétences et solidité technique."""
            return LLMResponse(content=mock_report, tokens_used=390)

        # Fallback response
        return LLMResponse(content="Simulated structured response based on evidence.", tokens_used=50)
