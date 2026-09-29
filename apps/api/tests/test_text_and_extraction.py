import pytest

from app.core.jsonutil import extract_json
from app.core.text import clip, detect_language, keywords, normalize_url
from app.services.embedding import EmbeddingService
from app.services.extractor import extract_document

ARTICLE_HTML = """<!doctype html><html><head>
<title>Site title | Example</title>
<meta property="og:title" content="Post-quantum cryptography explained">
<meta name="description" content="A primer on PQC.">
<meta property="article:published_time" content="2025-03-14T09:00:00Z">
<meta name="author" content="Ada Lovelace">
</head><body>
<header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
<div class="cookie-banner">We use cookies. Accept?</div>
<article>
  <h1>Post-quantum cryptography explained</h1>
  <p>Post-quantum cryptography (PQC) refers to algorithms believed to be secure against quantum computers.</p>
  <p>NIST standardised ML-KEM and ML-DSA in 2024 after an eight-year process that evaluated dozens of candidates.</p>
  <ul><li>Larger keys than elliptic curves</li><li>Different performance trade-offs</li></ul>
  <p>Migration requires crypto-agility: systems must be able to swap algorithms without a full redesign of the protocol.</p>
</article>
<aside>Related posts</aside>
<footer>Copyright</footer>
<script>var tracking = true;</script>
</body></html>"""


def test_extract_document_keeps_article_and_metadata():
    doc = extract_document(ARTICLE_HTML, "https://www.example.com/pqc")
    assert doc.title == "Post-quantum cryptography explained"
    assert doc.domain == "example.com"
    assert doc.published_date.startswith("2025-03-14")
    assert doc.author == "Ada Lovelace"
    assert "ML-KEM" in doc.content and "crypto-agility" in doc.content
    assert "Larger keys" in doc.content
    for noise in ("cookies", "tracking", "Copyright", "About"):
        assert noise not in doc.content


def test_extract_plain_text():
    doc = extract_document("just   some text", "https://example.com/a.txt", content_type="text/plain")
    assert doc.content == "just some text"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 2}\n```', {"a": 2}),
        ('Here is the plan:\n{"a": 3}\nHope it helps!', {"a": 3}),
        ("\ufeff  [1, 2]", [1, 2]),
        ('noise {not json} then {"a": 4}', {"a": 4}),
    ],
)
def test_extract_json(raw, expected):
    assert extract_json(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "no json at all"])
def test_extract_json_errors(raw):
    with pytest.raises(ValueError):
        extract_json(raw)


def test_normalize_url_for_deduplication():
    a = normalize_url("https://WWW.Example.com/path/?utm_source=x&id=3#section")
    b = normalize_url("https://example.com/path?id=3")
    assert a == b


def test_language_detection_and_keywords():
    assert detect_language("Quels sont les avantages du télétravail ?") == "fr"
    assert detect_language("What are the benefits of remote work?") == "en"
    assert detect_language("énergie nucléaire France") == "fr"
    assert keywords("What are the tradeoffs of post-quantum cryptography?") == ["tradeoffs", "post-quantum", "cryptography"]


def test_clip_only_adds_ellipsis_when_needed():
    assert clip("short", 10) == "short"
    assert clip("a" * 20, 10) == "a" * 9 + "…"


def test_embedding_similarity_is_meaningful():
    related_a = EmbeddingService.compute_embedding("Python programming for active learning")
    related_b = EmbeddingService.compute_embedding("python programs and project-based learning")
    unrelated = EmbeddingService.compute_embedding("quantum mechanics and astrophysics")
    assert len(related_a) == 256
    assert EmbeddingService.cosine_similarity(related_a, related_b) > 0.3
    assert EmbeddingService.cosine_similarity(related_a, unrelated) < 0.1
    # stop words alone carry no signal
    assert not any(EmbeddingService.compute_embedding("the of and is are"))
    assert EmbeddingService.cosine_similarity(related_a, [0.1] * 128) == 0.0
