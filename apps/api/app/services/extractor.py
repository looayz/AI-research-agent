import re
from typing import Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.core.text import domain_of

MAX_TEXT_CHARS = 20_000

_NOISE_TAGS = [
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "template",
    "nav",
    "footer",
    "header",
    "aside",
    "dialog",
]
_NOISE_ROLES = ("navigation", "banner", "contentinfo", "complementary", "search", "dialog")
_NOISE_HINT_RE = re.compile(
    r"(?:^|[\s_-])(?:cookies?|consent|newsletter|subscribe|advert|ads|promo|share|sharing|social|breadcrumbs?|related-posts)(?:[\s_-]|$)",
    re.I,
)
_NEVER_NOISE = frozenset({"html", "body", "main", "article"})
_BLOCK_TAGS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "td", "th", "dd", "dt", "figcaption"]
_DATE_META = (
    ("property", "article:published_time"),
    ("name", "article:published_time"),
    ("name", "date"),
    ("name", "pubdate"),
    ("name", "publish-date"),
    ("name", "dc.date"),
    ("name", "DC.date.issued"),
    ("name", "citation_publication_date"),
    ("itemprop", "datePublished"),
)
_JSONLD_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]{8,40})"')


class ExtractedContent(BaseModel):
    url: str
    title: str
    domain: str
    content: str
    description: Optional[str] = None
    published_date: Optional[str] = None
    author: Optional[str] = None


def _meta(soup: BeautifulSoup, attr: str, value: str) -> Optional[str]:
    tag = soup.find("meta", attrs={attr: value})
    content = tag.get("content") if tag else None
    return content.strip() if isinstance(content, str) and content.strip() else None


def _published_date(soup: BeautifulSoup, html: str) -> Optional[str]:
    for attr, value in _DATE_META:
        found = _meta(soup, attr, value)
        if found:
            return found[:40]
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag and isinstance(time_tag.get("datetime"), str):
        return time_tag["datetime"][:40]
    match = _JSONLD_DATE_RE.search(html)
    return match.group(1) if match else None


def _is_noise(tag) -> bool:
    if tag.name in _NEVER_NOISE:
        return False
    if tag.get("role") in _NOISE_ROLES or tag.get("aria-hidden") == "true":
        return True
    hints = " ".join(tag.get("class") or []) + " " + (tag.get("id") or "")
    return bool(hints.strip()) and bool(_NOISE_HINT_RE.search(hints))


def _main_container(soup: BeautifulSoup):
    for candidate in (soup.find("article"), soup.find("main"), soup.find(attrs={"role": "main"})):
        if candidate is not None and len(candidate.get_text(" ", strip=True)) > 400:
            return candidate
    return soup.body or soup


def _readable_text(container) -> str:
    blocks: list[str] = []
    for element in container.find_all(_BLOCK_TAGS):
        # Skip blocks nested in another captured block (li inside li, p in td...)
        if element.find_parent(_BLOCK_TAGS) is not None:
            continue
        text = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
        if len(text) >= 3:
            blocks.append(text)
    if not blocks:
        blocks = [re.sub(r"\s+", " ", container.get_text(" ", strip=True))]
    # Drop exact duplicate lines (repeated menus, footers that survived).
    return "\n".join(dict.fromkeys(b for b in blocks if b))


def extract_document(html: str, url: str, content_type: str = "text/html") -> ExtractedContent:
    domain = domain_of(url)
    if not content_type.startswith(("text/html", "application/xhtml")):
        text = re.sub(r"[ \t]+", " ", html).strip()
        return ExtractedContent(url=url, title=domain, domain=domain, content=text[:MAX_TEXT_CHARS])

    soup = BeautifulSoup(html, "html.parser")
    title = (
        _meta(soup, "property", "og:title")
        or (soup.title.get_text(strip=True) if soup.title else None)
        or (soup.h1.get_text(" ", strip=True) if soup.h1 else None)
        or domain
    )
    description = _meta(soup, "name", "description") or _meta(soup, "property", "og:description")
    author = _meta(soup, "name", "author")
    published = _published_date(soup, html)

    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        if not getattr(tag, "decomposed", False) and _is_noise(tag):
            tag.decompose()

    text = _readable_text(_main_container(soup))
    if len(text) < 200 and description and description not in text:
        text = f"{description}\n{text}".strip()

    return ExtractedContent(
        url=url,
        title=re.sub(r"\s+", " ", title)[:300],
        domain=domain,
        content=text[:MAX_TEXT_CHARS],
        description=description,
        published_date=published,
        author=author,
    )
