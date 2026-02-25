"""Wikipedia MediaWiki API fetch + HTML parsing for French Wikipedia."""

import re

import httpx
from bs4 import BeautifulSoup

_API_URL = "https://fr.wikipedia.org/w/api.php"
_HEADERS = {
    "User-Agent": "PedantixClone/1.0 (https://github.com/local/pedantix-clone; educational)"
}

# Minimum character length for a paragraph to be included
_MIN_PARA_LEN = 50


async def fetch_intro(title: str, max_paragraphs: int = 3) -> dict[str, str]:
    """Fetch the introduction section of a French Wikipedia article.

    Returns {"title": <canonical title>, "intro_text": <cleaned text>}.
    Raises httpx.HTTPError or KeyError on failure.
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "formatversion": "2",
        "format": "json",
        "section": "0",
    }
    async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
        resp = await client.get(_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise ValueError(f"MediaWiki error: {data['error'].get('info', data['error'])}")

    canonical_title: str = data["parse"]["title"]
    html: str = data["parse"]["text"]
    intro_text = _extract_intro(html, max_paragraphs=max_paragraphs)

    return {"title": canonical_title, "intro_text": intro_text}


# CSS classes that contain UI chrome, hatnotes, and maintenance banners
_SKIP_PARENT_CLASSES = {
    "hatnote",
    "bandeau-section",
    "bandeau",
    "dablink",
    "rellink",
    "bandeau-container",
    "bandeau-cell",
    "bandeau-article",
    "infobox",
    "notice",
    "plainlist",
    "navbox",
    "thumb",
    "mw-empty-elt",
}


def _is_in_skipped_container(tag) -> bool:
    """Return True if the tag has an ancestor with a skip class."""
    for parent in tag.parents:
        classes = parent.get("class") or []
        if any(c in _SKIP_PARENT_CLASSES for c in classes):
            return True
    return False


def _extract_intro(html: str, max_paragraphs: int = 3) -> str:
    """Parse MediaWiki HTML and extract clean introduction paragraphs."""
    soup = BeautifulSoup(html, "lxml")

    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        if len(paragraphs) >= max_paragraphs:
            break

        if _is_in_skipped_container(p):
            continue

        # Drop citation superscripts and pronunciation spans
        for sup in p.find_all("sup"):
            sup.decompose()

        text = p.get_text()

        # Remove bracket markers like [1], [note 2], [réf. nécessaire]
        text = re.sub(r"\[[^\]]{0,40}\]", "", text)

        # Strip any residual HTML/XML tags that leaked through (e.g. <ref>, <references/>)
        text = re.sub(r"<[^>]{0,200}>", "", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) >= _MIN_PARA_LEN:
            paragraphs.append(text)

    if not paragraphs:
        raise ValueError("No usable paragraphs found in Wikipedia article")

    return "\n\n".join(paragraphs)
