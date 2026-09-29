import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

STOPWORDS_EN = frozenset(
    """a about above after again against all am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have
    having he her here hers herself him himself his how i if in into is it its itself just me more most
    my myself no nor not now of off on once only or other our ours ourselves out over own same she should
    so some such than that the their theirs them themselves then there these they this those through to
    too under until up very was we were what when where which while who whom why will with would you your
    yours yourself yourselves vs versus via compare comparison between""".split()
)

STOPWORDS_FR = frozenset(
    """a afin ai aie aient ainsi alors au aucun aupres auquel aura aurait aussi autre autres aux avec avoir
    c ca car ce ceci cela celle celles celui cependant ces cet cette ceux chaque chez comme comment d dans de
    des donc dont du elle elles en entre est et etaient etait etre eu fait faut il ils j je jusqu l la le les
    leur leurs lors lorsque lui m ma mais me meme mes moi mon n ne ni nos notre nous on ont ou par parce
    pas peu peut plus pour pourquoi quand que quel quelle quelles quels qui quoi s sa sans se ses si son
    sont sous sur t ta te tes toi ton tous tout toute toutes tres tu un une vos votre vous y quelles""".split()
)

STOPWORDS = STOPWORDS_EN | STOPWORDS_FR

_FR_MARKERS = frozenset(
    (
        "le la les des est sont quels quelles quelle quel comment pourquoi une du et pour "
        "dans avec sur entre aux ces qui que faut"
    ).split()
)
_EN_MARKERS = frozenset("the is are what how why of and for in with which does do between their this that".split())
_WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """Lower-cased, accent-free word tokens (French elisions such as l' are split off)."""
    tokens = []
    for raw in _WORD_RE.findall(strip_accents(text.lower())):
        tokens.extend(part for part in raw.split("'") if part)
    return tokens


def detect_language(text: str) -> str:
    """Tiny heuristic, good enough to pick between English and French."""
    words = tokenize(text)
    fr = sum(w in _FR_MARKERS for w in words)
    en = sum(w in _EN_MARKERS for w in words)
    if fr == en:
        # Keyword-only text (e.g. search queries): French accents are a good hint.
        return "fr" if re.search(r"[éèêëàâçùûôîï]", text.lower()) else "en"
    return "fr" if fr > en else "en"


def keywords(text: str, limit: int = 8) -> list[str]:
    """Significant words of ``text`` in order of appearance, original casing kept."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in _WORD_RE.findall(text):
        for part in raw.split("'"):
            key = strip_accents(part.lower())
            if len(key) < 2 or key in STOPWORDS or key in seen:
                continue
            seen.add(key)
            out.append(part)
            if len(out) >= limit:
                return out
    return out


def clip(text: str | None, limit: int) -> str:
    """Truncate to ``limit`` characters, adding an ellipsis only when needed."""
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= limit else text[: max(limit - 1, 0)].rstrip() + "…"


_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref_src")


def normalize_url(url: str) -> str:
    """Canonical form used to de-duplicate sources (scheme/host case, fragments, tracking params)."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith(_TRACKING_PARAMS)]
    )
    path = parts.path.rstrip("/") or "/"
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def domain_of(url: str) -> str:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host
